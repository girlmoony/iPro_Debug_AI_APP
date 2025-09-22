# -*- coding: utf-8 -*-
"""
フォルダ比較＆差分反映ツール（Windows 共有/UNC 対応）
- ローカル構成を基準（相対パスで対応付け）
- 画像の存在/同名/内容（MD5）比較
- 差分をExcel出力
- 反映（コピー/上書き/任意で削除）
- 1回目チェックのみ → 問題なければ自動適用（--apply-if-clean）

要件:
    pip install pandas openpyxl
"""

import os
import sys
import argparse
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import pandas as pd


def parse_args():
    p = argparse.ArgumentParser(description="Local/Remote 画像フォルダ比較＆差分反映ツール")
    p.add_argument("--local", required=True, help="ローカルの基準ルート")
    p.add_argument("--remote", required=True, help="リモートの基準ルート（UNC可）")
    p.add_argument("--excel-out", default="compare_result.xlsx", help="Excel出力先ファイル")
    p.add_argument("--image-exts", default=".jpg,.jpeg,.png,.gif,.bmp,.tif,.tiff,.webp",
                   help="対象拡張子（小文字・カンマ区切り）例: .jpg,.png")
    # 反映系
    g = p.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="比較後に差分を適用する")
    g.add_argument("--first-pass-only", action="store_true", help="比較のみ（Excel出力まで）")
    g.add_argument("--apply-if-clean", action="store_true",
                   help="比較 → 問題が無ければ自動適用（問題があれば適用しない）")

    p.add_argument("--delete-local-extra", action="store_true",
                   help="ローカルにしか無い画像を削除（危険！既定は削除しない）")
    p.add_argument("--dry-run", action="store_true",
                   help="適用内容を表示のみ（コピー/削除は実行しない）")
    return p.parse_args()


def is_image(p: Path, image_exts: set) -> bool:
    return p.suffix.lower() in image_exts


def md5sum(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.md5()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""  # 読めないなどの問題


def collect_local_tree(local_root: Path) -> List[Path]:
    folders = []
    for dirpath, _, _ in os.walk(local_root):
        folders.append(Path(dirpath))
    return folders


def comparable_images_in(folder: Path, image_exts: set) -> List[Path]:
    try:
        return [p for p in folder.iterdir() if p.is_file() and is_image(p, image_exts)]
    except Exception:
        return []


def to_rel(p: Path, root: Path) -> Path:
    try:
        return p.relative_to(root)
    except Exception:
        return p


def is_clean_plan(df_folders: pd.DataFrame,
                  df_files: pd.DataFrame,
                  df_plan: pd.DataFrame,
                  delete_local_extra: bool) -> Tuple[bool, List[str]]:
    """
    "問題なし" の判定。
    - RemoteMissing フォルダがある → 問題
    - MD5 が空（読み出し不可）なファイルがある → 問題
    - delete_local_extra 指定時、DELETE_LOCAL アクションが含まれる → 追加確認が必要とみなし問題
    """
    reasons = []

    # 1) リモートに対応フォルダが無い
    if not df_folders.empty:
        missing = df_folders[df_folders["folder_status"] == "RemoteMissing"]
        if not missing.empty:
            reasons.append(f"リモートに無いフォルダが {len(missing)} 件あります")

    # 2) ハッシュ計算不可
    if not df_files.empty:
        unreadable = df_files[(df_files["local_exists"] & (df_files["local_md5"] == "")) |
                              (df_files["remote_exists"] & (df_files["remote_md5"] == ""))]
        if not unreadable.empty:
            reasons.append(f"ハッシュが空（読み出し失敗）のファイルが {len(unreadable)} 件あります")

    # 3) 削除アクション（安全側に抑止）
    if delete_local_extra:
        if not df_plan.empty and (df_plan["action"] == "DELETE_LOCAL").any():
            reasons.append("ローカル削除アクションが含まれています（--delete-local-extra 指定）")

    return (len(reasons) == 0, reasons)


def main():
    args = parse_args()

    LOCAL_ROOT = Path(args.local)
    REMOTE_ROOT = Path(args.remote)
    EXCEL_OUT = args.excel_out
    IMAGE_EXTS = {ext.strip().lower() for ext in args.image_exts.split(",") if ext.strip()}

    if not LOCAL_ROOT.exists():
        print(f"[ERROR] LOCAL_ROOT が存在しません: {LOCAL_ROOT}")
        sys.exit(1)

    start_ts = datetime.now()

    # 収集
    records = []      # ファイル粒度
    folder_rows = []  # フォルダ粒度

    local_folders = collect_local_tree(LOCAL_ROOT)

    for lf in local_folders:
        rel = to_rel(lf, LOCAL_ROOT)
        rf = REMOTE_ROOT / rel
        remote_exists = rf.exists() and rf.is_dir()

        folder_rows.append({
            "rel_folder": str(rel).replace("\\", "/"),
            "local_path": str(lf),
            "remote_path": str(rf),
            "folder_status": "Match" if remote_exists else "RemoteMissing",
        })

        local_imgs = comparable_images_in(lf, IMAGE_EXTS)

        remote_imgs_index: Dict[str, Path] = {}
        if remote_exists:
            for rp in comparable_images_in(rf, IMAGE_EXTS):
                remote_imgs_index[rp.name.lower()] = rp

        # ローカル基準で同名ファイルの比較
        for li in local_imgs:
            rel_file = to_rel(li, LOCAL_ROOT)
            li_key = li.name.lower()
            ri = remote_imgs_index.get(li_key)

            local_exists = True
            remote_exists_file = ri is not None

            li_size = li.stat().st_size if li.exists() else None
            li_mtime = datetime.fromtimestamp(li.stat().st_mtime) if li.exists() else None
            ri_size = ri.stat().st_size if (ri is not None and ri.exists()) else None
            ri_mtime = datetime.fromtimestamp(ri.stat().st_mtime) if (ri is not None and ri.exists()) else None

            if not remote_exists_file:
                cmp = "MissingOnRemote"
                same = False
                li_md5 = md5sum(li)
                ri_md5 = ""
            else:
                li_md5 = md5sum(li)
                ri_md5 = md5sum(ri)
                same = (li_md5 != "" and li_md5 == ri_md5)
                cmp = "Same" if same else "Different"

            records.append({
                "rel_path": str(rel_file).replace("\\", "/"),
                "file_name": li.name,
                "folder_rel": str(rel).replace("\\", "/"),
                "local_path": str(li),
                "remote_path": str(ri) if ri is not None else "",
                "local_exists": local_exists,
                "remote_exists": remote_exists_file,
                "compare_result": cmp,
                "same_content": same,
                "local_size": li_size,
                "remote_size": ri_size,
                "local_mtime": li_mtime,
                "remote_mtime": ri_mtime,
                "local_md5": li_md5,
                "remote_md5": ri_md5,
            })

        # リモートにのみある画像 → ローカル取り込み候補
        if remote_exists:
            local_names = {p.name.lower() for p in local_imgs}
            for ri_name_key, ri in remote_imgs_index.items():
                if ri.name.lower() not in local_names:
                    rel_file_remote = ri.relative_to(REMOTE_ROOT)
                    records.append({
                        "rel_path": str(rel_file_remote).replace("\\", "/"),
                        "file_name": ri.name,
                        "folder_rel": str(rel).replace("\\", "/"),
                        "local_path": str(lf / ri.name),
                        "remote_path": str(ri),
                        "local_exists": False,
                        "remote_exists": True,
                        "compare_result": "MissingOnLocal",
                        "same_content": False,
                        "local_size": None,
                        "remote_size": ri.stat().st_size if ri.exists() else None,
                        "local_mtime": None,
                        "remote_mtime": datetime.fromtimestamp(ri.stat().st_mtime) if ri.exists() else None,
                        "local_md5": "",
                        "remote_md5": md5sum(ri),
                    })

    df_files = pd.DataFrame.from_records(records)
    df_folders = pd.DataFrame.from_records(folder_rows)

    # 反映プラン生成
    plan_rows = []
    for row in records:
        action = "NONE"
        reason = ""
        if row["compare_result"] == "MissingOnLocal" and row["remote_exists"]:
            action = "COPY_REMOTE_TO_LOCAL"
            reason = "ローカルに無い → 取り込み"
        elif row["compare_result"] == "Different" and row["remote_exists"] and row["local_exists"]:
            action = "OVERWRITE_LOCAL_WITH_REMOTE"
            reason = "同名だが内容差分 → 上書き"
        elif row["compare_result"] == "MissingOnRemote" and args.delete_local_extra:
            action = "DELETE_LOCAL"
            reason = "ローカルのみ（削除フラグ有効時）"
        else:
            action = "NONE"
            reason = "変更なし/対象外"

        plan_rows.append({
            "rel_path": row["rel_path"],
            "file_name": row["file_name"],
            "action": action,
            "reason": reason,
            "local_path": row["local_path"],
            "remote_path": row["remote_path"]
        })

    df_plan = pd.DataFrame.from_records(plan_rows)

    # Excel 出力
    with pd.ExcelWriter(EXCEL_OUT, engine="openpyxl") as xw:
        if not df_folders.empty:
            df_folders.sort_values("rel_folder").to_excel(xw, sheet_name="Folders", index=False)
        if not df_files.empty:
            df_files.sort_values("rel_path").to_excel(xw, sheet_name="Files", index=False)
        df_plan[df_plan["action"] != "NONE"].sort_values("rel_path").to_excel(xw, sheet_name="PlannedActions", index=False)

    print(f"[INFO] Excel 出力: {EXCEL_OUT}")

    # --- 適用フロー制御 ---
    will_apply = False
    apply_reason = ""

    if args.first_pass_only:
        will_apply = False
        apply_reason = "--first-pass-only 指定のため適用しません"
    elif args.apply:
        will_apply = True
        apply_reason = "--apply 指定のため適用します"
    elif args.apply_if_clean:
        clean, reasons = is_clean_plan(df_folders, df_files, df_plan, args.delete_local_extra)
        if clean:
            will_apply = True
            apply_reason = "--apply-if-clean：問題なし判定のため適用します"
        else:
            will_apply = False
            apply_reason = "--apply-if-clean：問題が検出されたため適用しません\n  - " + "\n  - ".join(reasons)
    else:
        # 既定は適用しない（レポートのみ）
        will_apply = False
        apply_reason = "既定（チェックのみ）。適用するには --apply か --apply-if-clean を指定してください"

    print(f"[INFO] 適用可否: {will_apply}  ({apply_reason})")

    # --- 適用実行 ---
    if will_apply:
        applied = []
        errors = []

        def ensure_parent(path_str: str):
            p = Path(path_str)
            p.parent.mkdir(parents=True, exist_ok=True)

        for _, r in df_plan.iterrows():
            act = r["action"]
            if act == "NONE":
                continue

            lp = Path(r["local_path"]) if r["local_path"] else None
            rp = Path(r["remote_path"]) if r["remote_path"] else None

            try:
                if act in ("COPY_REMOTE_TO_LOCAL", "OVERWRITE_LOCAL_WITH_REMOTE"):
                    if not rp or not rp.exists():
                        raise FileNotFoundError(f"remote not found: {rp}")
                    ensure_parent(str(lp))
                    if args.dry_run:
                        print(f"[DRY] {act}  {rp} -> {lp}")
                    else:
                        shutil.copy2(rp, lp)
                    applied.append((act, str(rp), str(lp)))
                elif act == "DELETE_LOCAL":
                    if lp and lp.exists():
                        if args.dry_run:
                            print(f"[DRY] DELETE  {lp}")
                        else:
                            lp.unlink()
                        applied.append((act, "", str(lp)))
                else:
                    continue
            except Exception as e:
                errors.append((act, str(lp) if lp else "", str(rp) if rp else "", repr(e)))

        # 結果追記
        with pd.ExcelWriter(EXCEL_OUT, engine="openpyxl", mode="a", if_sheet_exists="replace") as xw:
            if applied:
                pd.DataFrame(applied, columns=["action", "src_remote", "dst_local"]).to_excel(xw, sheet_name="Applied", index=False)
            else:
                pd.DataFrame({"info": ["No actions executed (nothing to apply or DRY_RUN)"]}).to_excel(xw, sheet_name="Applied", index=False)
            if errors:
                pd.DataFrame(errors, columns=["action", "local_path", "remote_path", "error"]).to_excel(xw, sheet_name="Errors", index=False)

        print(f"[INFO] 適用完了（dry-run={args.dry_run}）")

    dur = datetime.now() - start_ts
    print(f"[DONE] 終了。処理時間: {dur}")


if __name__ == "__main__":
    main()

# 1回目：チェックのみ（Excelを見て確認）
python sync_images.py ^
  --local "D:\local folder" ^
  --remote "\\SERVER\Share\remote folder" ^
  --excel-out "compare_result.xlsx" ^
  --first-pass-only

# 2回目：問題なければ自動で適用（コピー/上書き）
python sync_images.py ^
  --local "D:\local folder" ^
  --remote "\\SERVER\Share\remote folder" ^
  --excel-out "compare_result.xlsx" ^
  --apply-if-clean

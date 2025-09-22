# -*- coding: utf-8 -*-
"""
フォルダ比較＆差分反映ツール（Windows 共有/UNC 対応）
- ローカル構成を基準（ローカル配下に存在するフォルダを対象）
- 画像ファイル（拡張子指定）の存在・内容（MD5）比較
- 差分をExcel出力
- 差分のローカル反映（コピー/上書き、必要なら削除）

要件:
    pip install pandas openpyxl  # または xlsxwriter

注意:
    - リモートはUNCやマップドドライブ等、Pythonから直接参照可能であること
    - 権限・ロック中ファイル・超大容量のハッシュ計算に注意
"""

import os
import sys
import hashlib
import shutil
from pathlib import Path
from datetime import datetime
import pandas as pd
from typing import Dict, Tuple, List

# ========= 設定 =========
# 例: r"\\SERVER\Share\RemoteFolder" もしくは "Z:\\RemoteFolder"
REMOTE_ROOT = r"\\SERVER\Share\RemoteFolder"     # ★編集
LOCAL_ROOT  = r"D:\Work\LocalFolder"             # ★編集

# 対象とする画像拡張子（小文字で記載）
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tif", ".tiff", ".webp"}

# Excel 出力先
EXCEL_OUT = "compare_result.xlsx"

# 反映動作（ローカルへ適用）
APPLY_DIFFS = True                # True: 差分をローカルへ反映する / False: レポートのみ
DELETE_LOCAL_EXTRA = False        # True: ローカルにしか無い画像を削除（危険）/ 既定 False
DRY_RUN = False                   # True: 反映内容を表示のみ（コピー/削除は実行しない）
# =======================


def is_image(p: Path) -> bool:
    return p.suffix.lower() in IMAGE_EXTS


def md5sum(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """大きなファイルも考慮したMD5計算。アクセス不可時は空文字を返す。"""
    h = hashlib.md5()
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(chunk_size), b""):
                h.update(chunk)
        return h.hexdigest()
    except Exception:
        return ""


def collect_local_tree(local_root: Path) -> List[Path]:
    """ローカルの基準フォルダ配下に存在する全サブフォルダ（自分含む）を返す。"""
    folders = []
    for dirpath, dirnames, filenames in os.walk(local_root):
        folders.append(Path(dirpath))
    return folders


def comparable_images_in(folder: Path) -> List[Path]:
    """フォルダ内の画像ファイル（直下のみ。サブフォルダは別途走査）"""
    try:
        return [p for p in folder.iterdir() if p.is_file() and is_image(p)]
    except Exception:
        return []


def to_rel(p: Path, root: Path) -> Path:
    try:
        return p.relative_to(root)
    except Exception:
        return p


def main():
    start_ts = datetime.now()
    local_root = Path(LOCAL_ROOT)
    remote_root = Path(REMOTE_ROOT)

    if not local_root.exists():
        print(f"[ERROR] LOCAL_ROOT が存在しません: {local_root}")
        sys.exit(1)

    # レコード蓄積
    records = []   # 画像単位
    folder_rows = []  # フォルダ単位要約

    # ローカル基準で全フォルダ列挙
    local_folders = collect_local_tree(local_root)

    for lf in local_folders:
        rel = to_rel(lf, local_root)
        rf = remote_root / rel
        remote_exists = rf.exists() and rf.is_dir()

        # 1) フォルダ名一致（=同じ相対パスのフォルダがリモートに存在するか）
        folder_status = "Match" if remote_exists else "RemoteMissing"
        folder_rows.append({
            "rel_folder": str(rel).replace("\\", "/"),
            "local_path": str(lf),
            "remote_path": str(rf),
            "folder_status": folder_status
        })

        # 2) フォルダ内の画像チェック（ローカル側に存在する画像が基準）
        local_imgs = comparable_images_in(lf)

        # リモート側にも画像があるかを把握（名前→Path）
        remote_imgs_index: Dict[str, Path] = {}
        if remote_exists:
            for rp in comparable_images_in(rf):
                remote_imgs_index[rp.name.lower()] = rp

        # a) ローカルの各画像について存在 & 内容比較
        for li in local_imgs:
            rel_file = to_rel(li, local_root)
            li_name_key = li.name.lower()
            ri = remote_imgs_index.get(li_name_key)

            local_exists = True
            remote_exists_file = ri is not None

            li_size = li.stat().st_size if li.exists() else None
            li_mtime = datetime.fromtimestamp(li.stat().st_mtime) if li.exists() else None
            ri_size = ri.stat().st_size if ri is not None and ri.exists() else None
            ri_mtime = datetime.fromtimestamp(ri.stat().st_mtime) if ri is not None and ri.exists() else None

            if not remote_exists_file:
                cmp = "MissingOnRemote"
                same = False
                li_md5 = md5sum(li)
                ri_md5 = ""
            else:
                # 3) 同名 → 中身比較（MD5）
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

        # b) リモートにだけ存在する画像（ローカルに無いもの） → ローカルへ取り込み候補
        if remote_exists:
            local_names = {p.name.lower() for p in local_imgs}
            for ri_name_key, ri in remote_imgs_index.items():
                if ri.name.lower() not in local_names:
                    rel_file_remote = ri.relative_to(remote_root)
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

    # DataFrame 化
    df_files = pd.DataFrame.from_records(records)
    df_folders = pd.DataFrame.from_records(folder_rows)

    # 反映計画（ローカル基準）
    # - MissingOnLocal: リモート→ローカルへコピー
    # - Different: リモートの内容でローカルを上書き（ローカルを基準構成として“差分反映”する解釈）
    # - MissingOnRemote: 既定では何もしない（必要ならローカル削除もあり得るが要注意）
    plan_rows = []
    for row in records:
        action = "None"
        reason = ""
        if row["compare_result"] == "MissingOnLocal" and row["remote_exists"]:
            action = "COPY_REMOTE_TO_LOCAL"
            reason = "ローカルに無い → 取り込み"
        elif row["compare_result"] == "Different" and row["remote_exists"] and row["local_exists"]:
            action = "OVERWRITE_LOCAL_WITH_REMOTE"
            reason = "同名だが内容差分 → 上書き"
        elif row["compare_result"] == "MissingOnRemote" and DELETE_LOCAL_EXTRA:
            action = "DELETE_LOCAL"
            reason = "ローカルのみ（削除フラグ有効時）"
        else:
            action = "NONE"
            reason = reason or "変更なし/対象外"

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
        df_folders.sort_values("rel_folder").to_excel(xw, sheet_name="Folders", index=False)
        df_files.sort_values("rel_path").to_excel(xw, sheet_name="Files", index=False)
        df_plan[df_plan["action"] != "NONE"].sort_values("rel_path").to_excel(xw, sheet_name="PlannedActions", index=False)

    print(f"[INFO] Excel 出力: {EXCEL_OUT}")

    # 差分のローカル反映
    if APPLY_DIFFS:
        applied = []
        errors = []

        # フォルダ作成（コピー先の親ディレクトリ）
        def ensure_parent(path_str: str):
            p = Path(path_str)
            p.parent.mkdir(parents=True, exist_ok=True)

        for _, r in df_plan.iterrows():
            act = r["action"]
            lp = Path(r["local_path"]) if r["local_path"] else None
            rp = Path(r["remote_path"]) if r["remote_path"] else None

            try:
                if act == "COPY_REMOTE_TO_LOCAL":
                    if rp and rp.exists():
                        ensure_parent(str(lp))
                        if DRY_RUN:
                            print(f"[DRY] COPY  {rp} -> {lp}")
                        else:
                            shutil.copy2(rp, lp)
                        applied.append((act, str(rp), str(lp)))
                elif act == "OVERWRITE_LOCAL_WITH_REMOTE":
                    if rp and rp.exists():
                        ensure_parent(str(lp))
                        if DRY_RUN:
                            print(f"[DRY] OVERWRITE  {rp} -> {lp}")
                        else:
                            shutil.copy2(rp, lp)
                        applied.append((act, str(rp), str(lp)))
                elif act == "DELETE_LOCAL":
                    if lp and lp.exists():
                        if DRY_RUN:
                            print(f"[DRY] DELETE  {lp}")
                        else:
                            lp.unlink()
                        applied.append((act, "", str(lp)))
                else:
                    continue
            except Exception as e:
                errors.append((act, str(lp), str(rp), repr(e)))

        # 反映結果を追記出力
        applied_df = pd.DataFrame(applied, columns=["action", "src_remote", "dst_local"])
        errors_df = pd.DataFrame(errors, columns=["action", "local_path", "remote_path", "error"])

        with pd.ExcelWriter(EXCEL_OUT, engine="openpyxl", mode="a", if_sheet_exists="replace") as xw:
            if not applied_df.empty:
                applied_df.to_excel(xw, sheet_name="Applied", index=False)
            else:
                pd.DataFrame({"info": ["No actions executed (nothing to apply or DRY_RUN)"]}).to_excel(xw, sheet_name="Applied", index=False)

            if not errors_df.empty:
                errors_df.to_excel(xw, sheet_name="Errors", index=False)

        print(f"[INFO] 反映完了（APPLY_DIFFS={APPLY_DIFFS}, DRY_RUN={DRY_RUN}, DELETE_LOCAL_EXTRA={DELETE_LOCAL_EXTRA})")

    dur = datetime.now() - start_ts
    print(f"[DONE] 終了。処理時間: {dur}")


if __name__ == "__main__":
    main()

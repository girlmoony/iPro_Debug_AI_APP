# -*- coding: utf-8 -*-
"""
ローカル基準：画像フォルダ差分レポート & 実行（DRY-RUN対応）

機能
- サブフォルダを含め、ローカルとリモートの「相対フォルダ」を突合
  - Match（両方にある）/ LocalOnly / RemoteOnly を判定
  - LocalOnly/RemoteOnly はそのフォルダ直下の画像数を計数してExcelに出力
- Matchフォルダ内は画像ファイルを
  - ファイル名一致 → 内容（MD5）比較
  - ローカルのみ／リモートのみ／内容差分 を抽出
- アクション計画を生成
  - RemoteOnly フォルダの画像 → コピー
  - Match で MissingOnLocal → コピー
  - Match で Different → 上書き（オプション）
  - Match で MissingOnRemote → 削除（オプション）
  - LocalOnly フォルダの画像 → 削除（オプション）
- Excel出力：FolderSummary / FileDiffs / PlannedActions / Applied / Errors

前提
    pip install pandas openpyxl

注意
- リモートは UNC（例：\\SERVER\Share）やマップドドライブで Python から参照可能であること
- 削除系フラグは慎重に。まずは --dry-run で確認してください
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
    p = argparse.ArgumentParser(description="ローカル基準 画像フォルダ差分 & 同期ツール")
    p.add_argument("--local", required=True, help="ローカル基準ルート（例：D:\\local folder）")
    p.add_argument("--remote", required=True, help="リモート基準ルート（例：\\\\SERVER\\Share\\remote folder）")
    p.add_argument("--excel-out", default="compare_result.xlsx", help="Excel出力先")
    p.add_argument("--image-exts", default=".jpg,.jpeg,.png,.gif,.bmp,.tif,.tiff,.webp",
                   help="対象拡張子（小文字・カンマ区切り）例：.jpg,.png,.webp")

    # 実行系
    p.add_argument("--dry-run", action="store_true", help="DRY-RUN（実ファイル操作なし）")
    p.add_argument("--apply", action="store_true", help="計画を実行（コピー/上書き/削除）")

    # 振る舞い（既定は“安全寄り”）
    p.add_argument("--overwrite-different", action="store_true", default=True,
                   help="内容差分（Different）をリモート→ローカルへ上書き（既定ON）")
    p.add_argument("--no-overwrite-different", dest="overwrite-different", action="store_false",
                   help="内容差分を上書きしない")

    p.add_argument("--copy-remote-only", action="store_true", default=True,
                   help="RemoteOnly フォルダ/ファイルをローカルへコピー（既定ON）")
    p.add_argument("--no-copy-remote-only", dest="copy-remote-only", action="store_false",
                   help="RemoteOnly のコピーを行わない")

    p.add_argument("--delete-local-only", action="store_true",
                   help="LocalOnly フォルダ/ファイルを削除（既定OFF）※危険")
    p.add_argument("--delete-missing-on-remote", action="store_true",
                   help="Matchフォルダ内でリモートに無いローカルファイルを削除（既定OFF）※危険")

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
        return ""  # 読み出し不可など


def walk_dirs(root: Path) -> List[Path]:
    """root配下の全フォルダ（自分含む）"""
    res = []
    for dirpath, _, _ in os.walk(root):
        res.append(Path(dirpath))
    return res


def list_images(folder: Path, image_exts: set) -> List[Path]:
    """直下の画像のみ（サブフォルダは別で走査）"""
    try:
        return [p for p in folder.iterdir() if p.is_file() and is_image(p, image_exts)]
    except Exception:
        return []


def to_rel(p: Path, root: Path) -> Path:
    try:
        return p.relative_to(root)
    except Exception:
        return p


def main():
    args = parse_args()

    LOCAL_ROOT = Path(args.local)
    REMOTE_ROOT = Path(args.remote)
    EXCEL_OUT = args.excel_out
    IMAGE_EXTS = {e.strip().lower() for e in args.image_exts.split(",") if e.strip()}

    if not LOCAL_ROOT.exists():
        print(f"[ERROR] LOCAL_ROOT が存在しません: {LOCAL_ROOT}")
        sys.exit(1)
    if not REMOTE_ROOT.exists():
        print(f"[WARN] REMOTE_ROOT が見つかりません: {REMOTE_ROOT}（資格情報やパスを確認）")

    t0 = datetime.now()

    # --- フォルダ集合 ---
    local_dirs = walk_dirs(LOCAL_ROOT)
    remote_dirs = walk_dirs(REMOTE_ROOT) if REMOTE_ROOT.exists() else []

    local_rel_set = {to_rel(d, LOCAL_ROOT).as_posix() for d in local_dirs}
    remote_rel_set = {to_rel(d, REMOTE_ROOT).as_posix() for d in remote_dirs}

    all_rel_folders = sorted(local_rel_set | remote_rel_set)

    folder_rows = []
    file_rows = []

    # --- ループ（各相対フォルダ）---
    for rel in all_rel_folders:
        lf = (LOCAL_ROOT / rel)
        rf = (REMOTE_ROOT / rel)

        l_exists = lf.exists() and lf.is_dir()
        r_exists = rf.exists() and rf.is_dir()

        if l_exists and r_exists:
            status = "Match"
        elif l_exists and not r_exists:
            status = "LocalOnly"
        else:
            status = "RemoteOnly"

        l_imgs = list_images(lf, IMAGE_EXTS) if l_exists else []
        r_imgs = list_images(rf, IMAGE_EXTS) if r_exists else []

        folder_rows.append({
            "rel_folder": rel,
            "local_path": str(lf),
            "remote_path": str(rf),
            "folder_status": status,
            "local_img_count": len(l_imgs),
            "remote_img_count": len(r_imgs),
        })

        # フォルダが一致する場合のみ、ファイル比較を行う
        if status == "Match":
            r_index: Dict[str, Path] = {p.name.lower(): p for p in r_imgs}

            # ローカル基準：ローカルにある画像それぞれを比較
            for li in l_imgs:
                name_key = li.name.lower()
                ri = r_index.get(name_key)

                li_size = li.stat().st_size if li.exists() else None
                li_mtime = datetime.fromtimestamp(li.stat().st_mtime) if li.exists() else None

                if ri is None:
                    # リモートに無い（ローカルのみ）
                    file_rows.append({
                        "rel_path": f"{rel}/{li.name}",
                        "file_name": li.name,
                        "folder_rel": rel,
                        "local_path": str(li),
                        "remote_path": "",
                        "compare_result": "MissingOnRemote",
                        "local_size": li_size,
                        "remote_size": None,
                        "local_mtime": li_mtime,
                        "remote_mtime": None,
                        "local_md5": md5sum(li),
                        "remote_md5": "",
                    })
                else:
                    ri_size = ri.stat().st_size if ri.exists() else None
                    ri_mtime = datetime.fromtimestamp(ri.stat().st_mtime) if ri.exists() else None

                    l_md5 = md5sum(li)
                    r_md5 = md5sum(ri)
                    cmp = "Same" if (l_md5 and r_md5 and l_md5 == r_md5) else "Different"

                    file_rows.append({
                        "rel_path": f"{rel}/{li.name}",
                        "file_name": li.name,
                        "folder_rel": rel,
                        "local_path": str(li),
                        "remote_path": str(ri),
                        "compare_result": cmp,
                        "local_size": li_size,
                        "remote_size": ri_size,
                        "local_mtime": li_mtime,
                        "remote_mtime": ri_mtime,
                        "local_md5": l_md5,
                        "remote_md5": r_md5,
                    })

            # リモートにしかない画像（ローカルに無い）
            local_name_set = {p.name.lower() for p in l_imgs}
            for ri in r_imgs:
                if ri.name.lower() not in local_name_set:
                    file_rows.append({
                        "rel_path": f"{rel}/{ri.name}",
                        "file_name": ri.name,
                        "folder_rel": rel,
                        "local_path": str(lf / ri.name),
                        "remote_path": str(ri),
                        "compare_result": "MissingOnLocal",
                        "local_size": None,
                        "remote_size": ri.stat().st_size if ri.exists() else None,
                        "local_mtime": None,
                        "remote_mtime": datetime.fromtimestamp(ri.stat().st_mtime) if ri.exists() else None,
                        "local_md5": "",
                        "remote_md5": md5sum(ri),
                    })

        # フォルダが一致しない場合（LocalOnly/RemoteOnly）はファイル比較は行わず計数のみ
        # → 実行計画では個々のファイル単位で扱うため、ここで個別列挙は不要


    df_folders = pd.DataFrame(folder_rows)
    df_files = pd.DataFrame(file_rows)

    # --- 実行計画 ---
    plan_rows = []

    # 1) RemoteOnly フォルダ → 画像をローカルへコピー（オプション）
    if args.copy_remote_only:
        for row in folder_rows:
            if row["folder_status"] == "RemoteOnly":
                rf = Path(row["remote_path"])
                lf = Path(row["local_path"])
                for rp in list_images(rf, IMAGE_EXTS):
                    plan_rows.append({
                        "action": "COPY_REMOTE_TO_LOCAL",
                        "reason": "RemoteOnly フォルダ取り込み",
                        "local_path": str(lf / rp.name),
                        "remote_path": str(rp),
                        "rel_path": f'{row["rel_folder"]}/{rp.name}',
                    })

    # 2) Match 内：MissingOnLocal → コピー
    for r in file_rows:
        if r["compare_result"] == "MissingOnLocal":
            plan_rows.append({
                "action": "COPY_REMOTE_TO_LOCAL",
                "reason": "ローカルに無いため取り込み",
                "local_path": r["local_path"],
                "remote_path": r["remote_path"],
                "rel_path": r["rel_path"],
            })

    # 3) Match 内：Different → 上書き（オプション：既定ON）
    if args.overwrite_different:
        for r in file_rows:
            if r["compare_result"] == "Different":
                plan_rows.append({
                    "action": "OVERWRITE_LOCAL_WITH_REMOTE",
                    "reason": "同名・内容差分のため上書き",
                    "local_path": r["local_path"],
                    "remote_path": r["remote_path"],
                    "rel_path": r["rel_path"],
                })

    # 4) Match 内：MissingOnRemote → ローカル削除（オプション）
    if args.delete_missing_on_remote:
        for r in file_rows:
            if r["compare_result"] == "MissingOnRemote":
                plan_rows.append({
                    "action": "DELETE_LOCAL_FILE",
                    "reason": "リモートに無い（--delete-missing-on-remote）",
                    "local_path": r["local_path"],
                    "remote_path": "",
                    "rel_path": r["rel_path"],
                })

    # 5) LocalOnly フォルダ → ローカル削除（オプション）
    if args.delete_local_only:
        for row in folder_rows:
            if row["folder_status"] == "LocalOnly":
                lf = Path(row["local_path"])
                for lp in list_images(lf, IMAGE_EXTS):
                    plan_rows.append({
                        "action": "DELETE_LOCAL_FILE",
                        "reason": "LocalOnly フォルダ（--delete-local-only）",
                        "local_path": str(lp),
                        "remote_path": "",
                        "rel_path": f'{row["rel_folder"]}/{lp.name}',
                    })

    df_plan = pd.DataFrame(plan_rows)

    # --- Excel 出力 ---
    with pd.ExcelWriter(EXCEL_OUT, engine="openpyxl") as xw:
        if not df_folders.empty:
            df_folders.sort_values(["folder_status", "rel_folder"]).to_excel(
                xw, sheet_name="FolderSummary", index=False
            )
        if not df_files.empty:
            df_files.sort_values("rel_path").to_excel(
                xw, sheet_name="FileDiffs", index=False
            )
        if not df_plan.empty:
            df_plan.sort_values("rel_path").to_excel(
                xw, sheet_name="PlannedActions", index=False
            )

    print(f"[INFO] Excel 出力完了: {EXCEL_OUT}")

    # --- 実行 ---
    if not args.apply:
        print("[INFO] DRYモード（--apply未指定）。実ファイル操作は行いません。")
    else:
        applied = []
        errors = []

        def ensure_parent(path_str: str):
            p = Path(path_str)
            p.parent.mkdir(parents=True, exist_ok=True)

        for _, r in df_plan.iterrows():
            act = r["action"]
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
                elif act == "DELETE_LOCAL_FILE":
                    if not lp:
                        continue
                    if args.dry_run:
                        print(f"[DRY] DELETE_LOCAL  {lp}")
                    else:
                        if lp.exists():
                            lp.unlink()
                    applied.append((act, "", str(lp)))
                else:
                    # 想定外のアクションはスキップ
                    continue
            except Exception as e:
                errors.append((act, str(lp) if lp else "", str(rp) if rp else "", repr(e)))

        # 結果の追記
        with pd.ExcelWriter(EXCEL_OUT, engine="openpyxl", mode="a", if_sheet_exists="replace") as xw:
            if applied:
                pd.DataFrame(applied, columns=["action", "src_remote", "dst_local"]).to_excel(
                    xw, sheet_name="Applied", index=False
                )
            else:
                pd.DataFrame({"info": ["No actions executed (nothing to do or DRY)"]}).to_excel(
                    xw, sheet_name="Applied", index=False
                )
            if errors:
                pd.DataFrame(errors, columns=["action", "local_path", "remote_path", "error"]).to_excel(
                    xw, sheet_name="Errors", index=False
                )

        print(f"[INFO] 実行完了（apply={args.apply}, dry-run={args.dry_run}）")

    print(f"[DONE] 終了。処理時間: {datetime.now() - t0}")


if __name__ == "__main__":
    main()


:: まずは差分を確認（DRY-RUN：計画だけ。実ファイル操作なし）
python compare_sync_images.py ^
  --local "D:\local folder" ^
  --remote "\\SERVER\Share\remote folder" ^
  --excel-out "compare_result.xlsx" ^
  --dry-run

:: 差分を実行（既定動作：リモート→ローカルへコピー/上書き。削除はデフォルト無効）
python compare_sync_images.py ^
  --local "D:\local folder" ^
  --remote "\\SERVER\Share\remote folder" ^
  --excel-out "compare_result.xlsx" ^
  --apply

:: ローカルにしか無いフォルダ/画像も削除してミラーしたい場合（慎重に）
python compare_sync_images.py ^
  --local "D:\local folder" ^
  --remote "\\SERVER\Share\remote folder" ^
  --excel-out "compare_result.xlsx" ^
  --apply --delete-local-only --delete-missing-on-remote


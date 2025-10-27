#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excelのsheet1!A列にあるクラス名（例: XXXXX_CCCCCCC_XXXXXXXXXX / XXXXXXXX_CCCCCCCCCm_XXXXXXXXXX）を読み取り、
datasets/{train,val,test} をチェックしてパスを out シートに出力します。

拡張仕様（本版）:
1) まず元のクラス名そのもので {subset}/{class_name} が存在するか確認 → あればそのまま出力 (FOUND_ORIGINAL)
2) 見つからない場合、クラス名の真ん中のトークン（2番目）を抽出し、末尾 'm' を1回だけ外した middle_core で
   各 subset (= train/val/test) 直下のディレクトリを総当たり検索し、真ん中トークンが middle_core と一致するものをヒットとみなす
3) ヒットがあれば、各ヒットのフォルダ名を A列のクラス名（= input_name）にリネームする。
   - 既定は DRY-RUN で実際には変更を加えません（--apply 指定時のみリネームを実行）
   - 同名ディレクトリが既に存在する等のコンフリクト時はリネームをスキップし note に理由を記録
   - 実行しない場合は FOUND_BY_MIDDLE_DRYRUN、実行した場合は FOUND_BY_MIDDLE_RENAMED
4) ヒットがなければ NOT_FOUND_ALL

出力列: input_name, used_query, train_path, val_path, test_path, status, note
- train/val/test の各列には、(リネーム後の)最終的なパス（DRY-RUN時は想定パス）を ';' で連結して出力
"""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd


def extract_middle_token(name: str, strip_trailing_m: bool = True) -> Optional[str]:
    """クラス名から真ん中のトークン（2番目）を取り出す。strip_trailing_m=True の場合、末尾 'm' を1回だけ除去。"""
    parts = str(name).split("_")
    if len(parts) < 3:
        return None
    mid = parts[1]
    if strip_trailing_m and mid.endswith("m"):
        mid = mid[:-1]
    return mid


def list_dirs_one_level(base: Path) -> List[Path]:
    """base 直下のディレクトリのみ列挙"""
    try:
        return [p for p in base.iterdir() if p.is_dir()]
    except FileNotFoundError:
        return []


def check_paths_exact(base_dir: Path, class_name: str, subsets: List[str]) -> Dict[str, str]:
    """各 subset について base/subset/class_name が存在するかを確認して、存在すればそのパス、なければ空文字を返す。"""
    results: Dict[str, str] = {}
    for sb in subsets:
        candidate = base_dir / sb / class_name
        results[sb] = str(candidate) if candidate.exists() else ""
    return results


def find_dirs_by_middle(base_dir: Path, middle_core: str, subsets: List[str]) -> Dict[str, List[Path]]:
    """
    各 subset 直下を走査し、「ディレクトリ名を '_' で区切ったときの真ん中のトークン == middle_core」の
    ディレクトリ Path を全て収集。該当なしなら空リスト。
    """
    results: Dict[str, List[Path]] = {}
    for sb in subsets:
        root = base_dir / sb
        hits: List[Path] = []
        for d in list_dirs_one_level(root):
            parts = d.name.split("_")
            if len(parts) >= 3 and parts[1] == middle_core:
                hits.append(d)
        results[sb] = hits
    return results


def plan_and_maybe_rename(hits: Dict[str, List[Path]], target_name: str, apply: bool) -> (Dict[str, List[Path]], List[str]):
    """
    subset ごとのヒットを target_name にリネームする計画を立て、apply=True のときのみ実行。
    返り値:
      - new_paths: subset -> List[Path]（実行後 or 想定後のパス）
      - notes: 実行やコンフリクトに関するメモ（複数）
    """
    new_paths: Dict[str, List[Path]] = {}
    notes: List[str] = []
    for sb, paths in hits.items():
        updated_list: List[Path] = []
        for p in paths:
            parent = p.parent
            new_p = parent / target_name
            if p == new_p:
                # すでに目標名
                updated_list.append(new_p)
                continue
            if new_p.exists():
                # コンフリクト: 既に存在
                notes.append(f"[{sb}] skip: {p.name} -> {target_name} (already exists)")
                updated_list.append(p)  # 変更なし
                continue
            if apply:
                try:
                    p.rename(new_p)
                    notes.append(f"[{sb}] renamed: {p.name} -> {target_name}")
                    updated_list.append(new_p)
                except Exception as e:
                    notes.append(f"[{sb}] error: {p.name} -> {target_name} ({e})")
                    updated_list.append(p)  # 変更なし
            else:
                # DRY-RUN: 予定のみ
                notes.append(f"[{sb}] plan: {p.name} -> {target_name}")
                updated_list.append(new_p)  # 想定後のパス
        new_paths[sb] = updated_list
    return new_paths, notes


def main():
    parser = argparse.ArgumentParser(description="Excelのクラス名からdatasets内のパスを収集し、必要に応じてリネームします。")
    parser.add_argument("--excel", required=True, help="入力Excelファイルのパス（既存ワークブック）")
    parser.add_argument("--base", required=True, help="datasetsのベースディレクトリ（例: /srv/datasets または //server/share/datasets）")
    parser.add_argument("--sheet_in", default="sheet1", help="入力シート名（既定: sheet1）")
    parser.add_argument("--sheet_out", default="out", help="出力シート名（既定: out）")
    parser.add_argument("--col", default="A", help="クラス名が入っている列（既定: A）")
    parser.add_argument("--header", type=int, default=None, help="ヘッダ行の行番号（0始まり）。ヘッダ無しなら None（既定）")
    parser.add_argument("--start_row", type=int, default=0, help="読み取り開始の行番号（0始まり）。既定: 0（ワークシート先頭から）")
    parser.add_argument("--subsets", nargs="*", default=["train", "val", "test"], help="検索するサブセット（既定: train val test）")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--apply", action="store_true", help="DRY-RUNを無効化して、実際にリネームを実行します")
    g.add_argument("--dry-run", action="store_true", help="DRY-RUN（既定）。指定がなくてもDRY-RUNとして扱われます")
    args = parser.parse_args()

    excel_path = Path(args.excel)
    base_dir = Path(args.base)
    do_apply = bool(args.apply)  # --apply 指定時のみ実変更

    if not excel_path.exists():
        raise FileNotFoundError(f"Excelが見つかりません: {excel_path}")
    if not base_dir.exists():
        raise FileNotFoundError(f"datasetsベースが見つかりません: {base_dir}")

    # Excel読込（指定列のみ）
    df_all = pd.read_excel(excel_path, sheet_name=args.sheet_in, header=args.header, usecols=args.col)
    df_all.columns = ["class_name"]
    if args.start_row > 0:
        df_all = df_all.iloc[args.start_row :].reset_index(drop=True)

    df_all = df_all.dropna(subset=["class_name"])
    df_all["class_name"] = df_all["class_name"].astype(str).str.strip()
    df_all = df_all[df_all["class_name"] != ""].reset_index(drop=True)

    records: List[Dict[str, str]] = []
    for cls in df_all["class_name"]:
        # 1) 元名で厳密検索
        paths_exact = check_paths_exact(base_dir, cls, args.subsets)
        found_exact = any(paths_exact[sb] for sb in args.subsets)
        if found_exact:
            rec = {
                "input_name": cls,
                "used_query": cls,
                **{f"{sb}_path": paths_exact.get(sb, "") for sb in args.subsets},
                "status": "FOUND_ORIGINAL",
                "note": "",
            }
            records.append(rec)
            continue

        # 2) 真ん中トークン（末尾mを外す）で検索
        middle_core = extract_middle_token(cls, strip_trailing_m=True)
        if middle_core:
            hit_dirs = find_dirs_by_middle(base_dir, middle_core, args.subsets)
            found_mid = any(hit_dirs[sb] for sb in args.subsets)
            if found_mid:
                # リネーム計画（DRY-RUN or 実行）
                new_paths, notes = plan_and_maybe_rename(hit_dirs, cls, apply=do_apply)
                status = "FOUND_BY_MIDDLE_RENAMED" if do_apply else "FOUND_BY_MIDDLE_DRYRUN"
                rec = {
                    "input_name": cls,
                    "used_query": f"MIDDLE:{middle_core}",
                    **{f"{sb}_path": ";".join(str(p) for p in new_paths.get(sb, [])) for sb in args.subsets},
                    "status": status,
                    "note": " | ".join(notes),
                }
                records.append(rec)
                continue

        # 3) 何も見つからない
        rec = {
            "input_name": cls,
            "used_query": "",
            **{f"{sb}_path": "" for sb in args.subsets},
            "status": "NOT_FOUND_ALL",
            "note": "",
        }
        records.append(rec)

    out_df = pd.DataFrame.from_records(
        records,
        columns=["input_name", "used_query"] + [f"{sb}_path" for sb in args.subsets] + ["status", "note"]
    )

    # Excelの out シートに書き出し（既存ファイルを更新）
    with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        out_df.to_excel(writer, sheet_name=args.sheet_out, index=False)

    # 進捗出力
    print(("APPLY" if do_apply else "DRY-RUN") + f": Wrote {len(out_df)} rows to sheet '{args.sheet_out}' in {excel_path}")


if __name__ == "__main__":
    main()


python find_dataset_paths.py \
  --excel /path/to/workbook.xlsx \
  --base /srv/datasets \
  --sheet_in sheet1 \
  --sheet_out out \
  --apply

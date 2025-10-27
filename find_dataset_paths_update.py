#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excelのsheet1!A列にあるクラス名（例: XXXXX_CCCCCCC_XXXXXXXXXX / XXXXXXXX_CCCCCCCCCm_XXXXXXXXXX）を読み取り、
datasets/{train,val,test} をチェックしてパスを out シートに出力します。

挙動:
1) まず元のクラス名そのもので {subset}/{class_name} が存在するか確認
2) 見つからない場合、クラス名の真ん中のトークン（CCCC...）のみを取り出し、末尾 'm' を1回だけ外した値 middle_core を作成
   - 各 subset (= train/val/test) の直下にあるディレクトリ名を総当たりし、
     それぞれのディレクトリ名を "_" で3分割して真ん中トークンが middle_core と等しいものをヒットとみなす
   - 該当ディレクトリが複数ある場合は、';' 区切りで全て出力
3) それでも見つからなければ、パスは空のまま名前を出力

出力列: input_name, used_query, train_path, val_path, test_path, status
"""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
import pandas as pd


def extract_middle_token(name: str, strip_trailing_m: bool = True) -> str | None:
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


def check_paths_by_middle(base_dir: Path, middle_core: str, subsets: List[str]) -> Dict[str, str]:
    """
    各 subset 直下を走査し、「ディレクトリ名を '_' で区切ったときの真ん中のトークン == middle_core」の
    ディレクトリを全て拾って ';' で連結して返す。該当なしなら空文字。
    """
    results: Dict[str, str] = {}
    for sb in subsets:
        root = base_dir / sb
        hits: List[str] = []
        for d in list_dirs_one_level(root):
            parts = d.name.split("_")
            if len(parts) >= 3 and parts[1] == middle_core:
                hits.append(str(d))
        results[sb] = ";".join(hits)
    return results


def main():
    parser = argparse.ArgumentParser(description="Excelのクラス名からdatasets内のパスを収集してoutシートに書き出します。")
    parser.add_argument("--excel", required=True, help="入力Excelファイルのパス（既存ワークブック）")
    parser.add_argument("--base", required=True, help="datasetsのベースディレクトリ（例: /srv/datasets または //server/share/datasets）")
    parser.add_argument("--sheet_in", default="sheet1", help="入力シート名（既定: sheet1）")
    parser.add_argument("--sheet_out", default="out", help="出力シート名（既定: out）")
    parser.add_argument("--col", default="A", help="クラス名が入っている列（既定: A）")
    parser.add_argument("--header", type=int, default=None, help="ヘッダ行の行番号（0始まり）。ヘッダ無しなら None（既定）")
    parser.add_argument("--start_row", type=int, default=0, help="読み取り開始の行番号（0始まり）。既定: 0（ワークシート先頭から）")
    parser.add_argument("--subsets", nargs="*", default=["train", "val", "test"], help="検索するサブセット（既定: train val test）")
    args = parser.parse_args()

    excel_path = Path(args.excel)
    base_dir = Path(args.base)

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
            }
            records.append(rec)
            continue

        # 2) 真ん中トークン（末尾mを外す）で検索
        middle_core = extract_middle_token(cls, strip_trailing_m=True)
        if middle_core:
            paths_mid = check_paths_by_middle(base_dir, middle_core, args.subsets)
            found_mid = any(paths_mid[sb] for sb in args.subsets)
            if found_mid:
                rec = {
                    "input_name": cls,
                    "used_query": f"MIDDLE:{middle_core}",
                    **{f"{sb}_path": paths_mid.get(sb, "") for sb in args.subsets},
                    "status": "FOUND_BY_MIDDLE",
                }
                records.append(rec)
                continue

        # 3) 何も見つからない
        rec = {
            "input_name": cls,
            "used_query": "",
            **{f"{sb}_path": "" for sb in args.subsets},
            "status": "NOT_FOUND_ALL",
        }
        records.append(rec)

    out_df = pd.DataFrame.from_records(records, columns=["input_name", "used_query"] + [f"{sb}_path" for sb in args.subsets] + ["status"])

    # Excelの out シートに書き出し（既存ファイルを更新）
    with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        out_df.to_excel(writer, sheet_name=args.sheet_out, index=False)

    print(f"Wrote {len(out_df)} rows to sheet '{args.sheet_out}' in {excel_path}")


if __name__ == "__main__":
    main()

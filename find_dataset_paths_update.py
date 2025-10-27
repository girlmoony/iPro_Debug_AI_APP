#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excelのsheet1!A列にあるクラス名（例: AAAAA_BBBBBB_CCCCCCCCC / AAAAA_BBBBBBm_CCCCCCCCC）を読み取り、
datasets/{train,val,test} をチェック・整備し、結果を out シートに出力します。

ロジック:
1) 厳密一致: {subset}/{class_name} が存在 → そのまま出力 (FOUND_ORIGINAL)
2) 不一致時の再検索: 真ん中トークン（2番目；末尾 'm' を外す）= middle_core を用い、
   各 subset 直下のフォルダ名を総当たりし、フォルダ名の真ん中トークン（末尾 'm' を外したもの）が middle_core と一致 → ヒット
3) ヒットがあれば、各ヒットのフォルダ名を A列のクラス名（= input_name）へリネーム
   - 既定は DRY-RUN（--apply 指定時のみ実リネーム）
   - コンフリクトはスキップし note に記録
   - DRY-RUN: FOUND_BY_MIDDLE_DRYRUN / 実行: FOUND_BY_MIDDLE_RENAMED
4) 何も見つからなければ NOT_FOUND_ALL
5) 追加: 指定フォルダ直下（train/val/test）に「Excelに記載がない」フォルダがあればピックアップ
   - 既定は DRY-RUN（削除しない）→ DELETE_CANDIDATE_DRYRUN
   - --delete-apply 指定時のみ削除 → DELETE_DELETED
   - 対象は1階層直下のフォルダ（パターン不問）。Excelに無い名前で、かつ今回のリネーム計画のターゲット名にも含まれないもの。

出力列: input_name, used_query, train_path, val_path, test_path, status, note
"""
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Set
import pandas as pd


def extract_middle_token(name: str, strip_trailing_m: bool = True) -> Optional[str]:
    parts = str(name).split("_")
    if len(parts) < 3:
        return None
    mid = parts[1]
    if strip_trailing_m and mid.endswith("m"):
        mid = mid[:-1]
    return mid


def list_dirs_one_level(base: Path) -> List[Path]:
    try:
        return [p for p in base.iterdir() if p.is_dir()]
    except FileNotFoundError:
        return []


def check_paths_exact(base_dir: Path, class_name: str, subsets: List[str]) -> Dict[str, str]:
    results: Dict[str, str] = {}
    for sb in subsets:
        candidate = base_dir / sb / class_name
        results[sb] = str(candidate) if candidate.exists() else ""
    return results


def find_dirs_by_middle(base_dir: Path, middle_core: str, subsets: List[str]) -> Dict[str, List[Path]]:
    results: Dict[str, List[Path]] = {}
    for sb in subsets:
        root = base_dir / sb
        hits: List[Path] = []
        for d in list_dirs_one_level(root):
            parts = d.name.split("_")
            if len(parts) >= 3:
                mid = parts[1]
                if mid.endswith("m"):
                    mid_cmp = mid[:-1]
                else:
                    mid_cmp = mid
                if mid_cmp == middle_core:
                    hits.append(d)
        results[sb] = hits
    return results


def plan_and_maybe_rename(hits: Dict[str, List[Path]], target_name: str, apply: bool) -> (Dict[str, List[Path]], List[str]):
    new_paths: Dict[str, List[Path]] = {}
    notes: List[str] = []
    for sb, paths in hits.items():
        updated_list: List[Path] = []
        for p in paths:
            parent = p.parent
            new_p = parent / target_name
            if p == new_p:
                updated_list.append(new_p)
                continue
            if new_p.exists():
                notes.append(f"[{sb}] skip: {p.name} -> {target_name} (already exists)")
                updated_list.append(p)
                continue
            if apply:
                try:
                    p.rename(new_p)
                    notes.append(f"[{sb}] renamed: {p.name} -> {target_name}")
                    updated_list.append(new_p)
                except Exception as e:
                    notes.append(f"[{sb}] error: {p.name} -> {target_name} ({e})")
                    updated_list.append(p)
            else:
                notes.append(f"[{sb}] plan: {p.name} -> {target_name}")
                updated_list.append(new_p)
        new_paths[sb] = updated_list
    return new_paths, notes


def find_unlisted_dirs(base_dir: Path, subsets: List[str], protected_names: Set[str]) -> Dict[str, List[Path]]:
    results: Dict[str, List[Path]] = {}
    for sb in subsets:
        root = base_dir / sb
        cand: List[Path] = []
        for d in list_dirs_one_level(root):
            if d.name not in protected_names:
                cand.append(d)
        results[sb] = cand
    return results


def delete_or_plan(paths: Dict[str, List[Path]], apply: bool) -> (Dict[str, List[Path]], List[str]):
    notes: List[str] = []
    for sb, lst in paths.items():
        for p in lst:
            if apply:
                try:
                    if p.exists() and p.is_dir():
                        try:
                            next(p.iterdir())
                            notes.append(f"[{sb}] skip delete (not empty): {p.name}")
                        except StopIteration:
                            p.rmdir()
                            notes.append(f"[{sb}] deleted: {p.name}")
                    else:
                        notes.append(f"[{sb}] skip delete (missing): {p.name}")
                except Exception as e:
                    notes.append(f"[{sb}] error delete: {p.name} ({e})")
            else:
                notes.append(f"[{sb}] plan delete: {p.name}")
    return paths, notes


def main():
    parser = argparse.ArgumentParser(description="Excelのクラス名に基づき datasets を照合し、必要に応じてリネーム/削除（DRY-RUN対応）します。")
    parser.add_argument("--excel", required=True, help="入力Excelファイルのパス（既存ワークブック）")
    parser.add_argument("--base", required=True, help="datasetsのベースディレクトリ（例: /srv/datasets または //server/share/datasets）")
    parser.add_argument("--sheet_in", default="sheet1", help="入力シート名（既定: sheet1）")
    parser.add_argument("--sheet_out", default="out", help="出力シート名（既定: out）")
    parser.add_argument("--col", default="A", help="クラス名が入っている列（既定: A）")
    parser.add_argument("--header", type=int, default=None, help="ヘッダ行の行番号（0始まり）。ヘッダ無しなら None（既定）")
    parser.add_argument("--start_row", type=int, default=0, help="読み取り開始の行番号（0始まり）。既定: 0（ワークシート先頭から）")
    parser.add_argument("--subsets", nargs="*", default=["train", "val", "test"], help="検索するサブセット（既定: train val test）")
    g1 = parser.add_mutually_exclusive_group()
    g1.add_argument("--apply", action="store_true", help="DRY-RUNを無効化して、実際にリネームを実行します")
    g1.add_argument("--dry-run", action="store_true", help="DRY-RUN（既定）。指定がなくてもDRY-RUNとして扱われます")
    g2 = parser.add_mutually_exclusive_group()
    g2.add_argument("--delete-apply", action="store_true", help="DRY-RUNを無効化して、DELETE候補の削除を実行します（空ディレクトリのみ）")
    g2.add_argument("--delete-dry-run", action="store_true", help="DELETEもDRY-RUN（既定）")
    args = parser.parse_args()

    excel_path = Path(args.excel)
    base_dir = Path(args.base)
    do_apply = bool(args.apply)
    do_delete_apply = bool(args.delete_apply)

    if not excel_path.exists():
        raise FileNotFoundError(f"Excelが見つかりません: {excel_path}")
    if not base_dir.exists():
        raise FileNotFoundError(f"datasetsベースが見つかりません: {base_dir}")

    df_all = pd.read_excel(excel_path, sheet_name=args.sheet_in, header=args.header, usecols=args.col)
    df_all.columns = ["class_name"]
    if args.start_row > 0:
        df_all = df_all.iloc[args.start_row :].reset_index(drop=True)

    df_all = df_all.dropna(subset=["class_name"])
    df_all["class_name"] = df_all["class_name"].astype(str).str.strip()
    df_all = df_all[df_all["class_name"] != ""].reset_index(drop=True)

    excel_class_names: Set[str] = set(df_all["class_name"].tolist())
    protected_names: Set[str] = set(excel_class_names)

    records: List[Dict[str, str]] = []

    for cls in df_all["class_name"]:
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

        middle_core = extract_middle_token(cls, strip_trailing_m=True)
        if middle_core:
            hit_dirs = find_dirs_by_middle(base_dir, middle_core, args.subsets)
            found_mid = any(hit_dirs[sb] for sb in args.subsets)
            if found_mid:
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

        rec = {
            "input_name": cls,
            "used_query": "",
            **{f"{sb}_path": "" for sb in args.subsets},
            "status": "NOT_FOUND_ALL",
            "note": "",
        }
        records.append(rec)

    unlisted = find_unlisted_dirs(base_dir, args.subsets, protected_names=protected_names)
    unlisted_after, del_notes = delete_or_plan(unlisted, apply=do_delete_apply)

    for sb, paths in unlisted_after.items():
        for p in paths:
            status = "DELETE_DELETED" if do_delete_apply else "DELETE_CANDIDATE_DRYRUN"
            note_msgs = [n for n in del_notes if f"[{sb}]" in n and p.name in n]
            rec = {
                "input_name": p.name,
                "used_query": "DELETE_SCAN",
                **{f"{s}_path": (str(p) if s == sb else "") for s in args.subsets},
                "status": status,
                "note": " | ".join(note_msgs) if note_msgs else "",
            }
            records.append(rec)

    out_df = pd.DataFrame.from_records(
        records,
        columns=["input_name", "used_query"] + [f"{sb}_path" for sb in args.subsets] + ["status", "note"]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        out_df.to_excel(writer, sheet_name=args.sheet_out, index=False)

    mode1 = "APPLY" if do_apply else "DRY-RUN"
    mode2 = "DELETE-APPLY" if do_delete_apply else "DELETE-DRY-RUN"
    print(f"{mode1} / {mode2}: Wrote {len(out_df)} rows to sheet '{args.sheet_out}' in {excel_path}")


if __name__ == "__main__":
    main()

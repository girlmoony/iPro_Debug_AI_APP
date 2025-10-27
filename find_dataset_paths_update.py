#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import shutil
import datetime as dt
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
                mid_cmp = mid[:-1] if mid.endswith("m") else mid
                if mid_cmp == middle_core:
                    hits.append(d)
        results[sb] = hits
    return results

def plan_and_maybe_rename(hits: Dict[str, List[Path]], target_name: str, apply: bool) -> Tuple[Dict[str, List[Path]], List[str]]:
    new_paths: Dict[str, List[Path]] = {}
    notes: List[str] = []
    for sb, paths in hits.items():
        updated_list: List[Path] = []
        for p in paths:
            parent = p.parent
            new_p = parent / target_name
            if p == new_p:
                updated_list.append(new_p); continue
            if new_p.exists():
                notes.append(f"[{sb}] skip: {p.name} -> {target_name} (already exists)")
                updated_list.append(p); continue
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

def unique_dest_path(dest: Path) -> Path:
    if not dest.exists():
        return dest
    ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return dest.with_name(dest.name + f"_{ts}")

def move_or_plan(paths: Dict[str, List[Path]], move_to: Optional[Path], apply: bool) -> Tuple[Dict[str, List[Path]], List[str]]:
    notes: List[str] = []
    moved_paths: Dict[str, List[Path]] = {}
    for sb, lst in paths.items():
        moved_paths[sb] = []
        for p in lst:
            if move_to is None:
                notes.append(f"[{sb}] plan move (no --move-to): {p.name}")
                moved_paths[sb].append(p)
                continue
            dest_root = move_to / sb
            dest_root.mkdir(parents=True, exist_ok=True)
            dest = unique_dest_path(dest_root / p.name)
            if apply:
                try:
                    shutil.move(str(p), str(dest))
                    notes.append(f"[{sb}] moved: {p} -> {dest}")
                    moved_paths[sb].append(dest)
                except Exception as e:
                    notes.append(f"[{sb}] error move: {p.name} ({e})")
                    moved_paths[sb].append(p)
            else:
                notes.append(f"[{sb}] plan move: {p} -> {dest}")
                moved_paths[sb].append(dest)
    return moved_paths, notes

def find_unlisted_dirs(base_dir: Path, subsets: List[str], protected_names: Set[str], exclude_paths: Set[Path]) -> Dict[str, List[Path]]:
    results: Dict[str, List[Path]] = {}
    for sb in subsets:
        root = base_dir / sb
        cand: List[Path] = []
        for d in list_dirs_one_level(root):
            if d in exclude_paths:
                continue
            if d.name in protected_names:
                continue
            cand.append(d)
        results[sb] = cand
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--excel", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--sheet_in", default="sheet1")
    parser.add_argument("--sheet_out", default="out")
    parser.add_argument("--col", default="A")
    parser.add_argument("--header", type=int, default=None)
    parser.add_argument("--start_row", type=int, default=0)
    parser.add_argument("--subsets", nargs="*", default=["train", "val", "test"])
    g1 = parser.add_mutually_exclusive_group()
    g1.add_argument("--apply", action="store_true", help="真ん中トークン一致ヒットをA列名へリネームを実行（既定はDRY-RUN）")
    g1.add_argument("--dry-run", action="store_true", help="DRY-RUN（指定なしでもDRY-RUN）")
    parser.add_argument("--move-to", type=str, default=None, help="Excelに無いフォルダの移動先ディレクトリ（例: /srv/quarantine）")
    g2 = parser.add_mutually_exclusive_group()
    g2.add_argument("--move-apply", action="store_true", help="移動を実行（--move-to が必要）")
    g2.add_argument("--move-dry-run", action="store_true", help="移動もDRY-RUN（既定）")
    args = parser.parse_args()

    excel_path = Path(args.excel)
    base_dir = Path(args.base)
    do_apply = bool(args.apply)
    do_move_apply = bool(args.move_apply)
    move_to = Path(args.move_to).resolve() if args.move_to else None

    if not excel_path.exists():
        raise FileNotFoundError(f"Excelが見つかりません: {excel_path}")
    if not base_dir.exists():
        raise FileNotFoundError(f"datasetsベースが見つかりません: {base_dir}")
    if do_move_apply and move_to is None:
        raise ValueError("--move-apply を使う場合は --move-to を指定してください")

    df_all = pd.read_excel(excel_path, sheet_name=args.sheet_in, header=args.header, usecols=args.col)
    df_all.columns = ["class_name"]
    if args.start_row > 0:
        df_all = df_all.iloc[args.start_row :].reset_index(drop=True)
    df_all = df_all.dropna(subset=["class_name"])
    df_all["class_name"] = df_all["class_name"].astype(str).str.strip()
    df_all = df_all[df_all["class_name"] != ""].reset_index(drop=True)

    excel_class_names: Set[str] = set(df_all["class_name"].tolist())
    protected_names: Set[str] = set(excel_class_names)
    exclude_paths_for_move: Set[Path] = set()

    records: List[Dict[str, str]] = []

    for cls in df_all["class_name"]:
        exact = check_paths_exact(base_dir, cls, args.subsets)
        found_exact = any(exact[sb] for sb in args.subsets)
        if found_exact:
            for sb in args.subsets:
                if exact[sb]:
                    exclude_paths_for_move.add(Path(exact[sb]))
            records.append({
                "input_name": cls,
                "used_query": cls,
                **{f"{sb}_path": exact.get(sb, "") for sb in args.subsets},
                "status": "FOUND_ORIGINAL",
                "note": "",
            })
            continue

        middle_core = extract_middle_token(cls, strip_trailing_m=True)
        if middle_core:
            hits = find_dirs_by_middle(base_dir, middle_core, args.subsets)
            found_mid = any(hits[sb] for sb in args.subsets)
            if found_mid:
                for sb in args.subsets:
                    for p in hits.get(sb, []):
                        exclude_paths_for_move.add(p)
                new_paths, notes = plan_and_maybe_rename(hits, cls, apply=do_apply)
                status = "FOUND_BY_MIDDLE_RENAMED" if do_apply else "FOUND_BY_MIDDLE_DRYRUN"
                records.append({
                    "input_name": cls,
                    "used_query": f"MIDDLE:{middle_core}",
                    **{f"{sb}_path": ";".join(str(p) for p in new_paths.get(sb, [])) for sb in args.subsets},
                    "status": status,
                    "note": " | ".join(notes),
                })
                continue

        records.append({
            "input_name": cls,
            "used_query": "",
            **{f"{sb}_path": "" for sb in args.subsets},
            "status": "NOT_FOUND_ALL",
            "note": "",
        })

    unlisted = {}
    for sb in args.subsets:
        root = base_dir / sb
        lst = []
        for d in list_dirs_one_level(root):
            if d in exclude_paths_for_move:
                continue
            if d.name in protected_names:
                continue
            lst.append(d)
        unlisted[sb] = lst

    moved_preview, move_notes = move_or_plan(unlisted, move_to=move_to, apply=do_move_apply)

    for sb, paths in moved_preview.items():
        for p in paths:
            status = "MOVED" if do_move_apply else "MOVE_CANDIDATE_DRYRUN"
            note_msgs = [n for n in move_notes if f"[{sb}]" in n and (p.name in n or str(p) in n)]
            records.append({
                "input_name": p.name,
                "used_query": "MOVE_SCAN",
                **{f"{s}_path": (str(p) if s == sb else "") for s in args.subsets},
                "status": status,
                "note": " | ".join(note_msgs) if note_msgs else "",
            })

    out_df = pd.DataFrame.from_records(
        records,
        columns=["input_name", "used_query"] + [f"{sb}_path" for sb in args.subsets] + ["status", "note"]
    )

    with pd.ExcelWriter(excel_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
        out_df.to_excel(writer, sheet_name=args.sheet_out, index=False)

    mode1 = "APPLY" if do_move_apply else "DRY-RUN"
    mode2 = f"MOVE-{'APPLY' if do_move_apply else 'DRY-RUN'} to {move_to if move_to else '(none)'}"
    print(f"{mode2}: Wrote {len(out_df)} rows to sheet '{args.sheet_out}' in {excel_path}")

if __name__ == "__main__":
    main()
python find_dataset_paths_move.py \
  --excel /path/to/workbook.xlsx \
  --base /srv/datasets \
  --apply \
  --move-to /srv/quarantine \
  --move-apply

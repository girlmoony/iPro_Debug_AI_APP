# save as: make_mistake_sheets.py
import argparse
import os
import sys
import pandas as pd

def to_bool_series(s):
    """
    'True'/'False', 'TRUE'/'FALSE', 1/0, True/False を安全に bool へ。
    それ以外は NaN のまま。
    """
    if s is None:
        return None
    if s.dtype == bool:
        return s
    return s.astype(str).str.strip().str.lower().map(
        {"true": True, "false": False, "1": True, "0": False}
    )

def ensure_cols(df, cols):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"入力シートに必要列がありません: {missing}\n"
                         f"見つかった列: {list(df.columns)}")

def change_ext_to_png(path_str):
    # 画像名（png 別名列が必要とのことなので、拡張子だけ .png に置換）
    base = os.path.basename(str(path_str))
    root, _ = os.path.splitext(base)
    return root + ".png"

def main():
    ap = argparse.ArgumentParser(
        description="Excelの評価結果から、間違いペア集計(SheetA)と間違い画像一覧(SheetB)を出力します。"
    )
    ap.add_argument("--input", required=True, help="入力Excelファイル（評価元シートを含む）")
    ap.add_argument("--sheet", default=None, help="読み込むシート名（省略時は先頭シート）")
    ap.add_argument("--output", default=None, help="出力Excelファイル（省略時は入力を上書き）")
    ap.add_argument("--sheetA_name", default="SheetA_間違いペア", help="SheetA のシート名")
    ap.add_argument("--sheetB_name", default="SheetB_間違い画像", help="SheetB のシート名")
    args = ap.parse_args()

    in_path = args.input
    out_path = args.output or in_path  # 既存ファイルに追記（同名シートがあれば上書き）
    read_sheet = args.sheet

    # 期待列（質問文ベース）
    needed = [
        "fname", "true", "pred", "pred_score",
        "pred_top2", "pred_top2_score", "correct", "top2_correct"
    ]

    # Excel 読み込み
    if not os.path.exists(in_path):
        print(f"入力ファイルが見つかりません: {in_path}", file=sys.stderr)
        sys.exit(1)

    # 先頭シート or 指定シートを読み込む
    xl = pd.ExcelFile(in_path)
    if read_sheet is None:
        read_sheet = xl.sheet_names[0]

    df = pd.read_excel(in_path, sheet_name=read_sheet, engine="openpyxl")
    # 必要列チェック（不足しても true/pred があれば最低限は進める）
    ensure_cols(df, ["fname", "true", "pred"])
    # 任意列が無い場合は作る（NaN埋め）
    for c in needed:
        if c not in df.columns:
            df[c] = pd.NA

    # correct が無ければ true と pred の一致で作る
    if df["correct"].isna().all():
        df["correct"] = (df["true"].astype(str) == df["pred"].astype(str))
    else:
        df["correct"] = to_bool_series(df["correct"])

    # =============== ① SheetA：間違ったペアの集計（枚数カウント） ===============
    # 「Top1で間違い」＝ true != pred を基準にする（correct == False）
    mask_wrong_top1 = df["true"].astype(str) != df["pred"].astype(str)
    df_wrong = df[mask_wrong_top1].copy()

    # 集計（A列：クラス名 = true、B列：間違ったクラス名 = pred、枚数）
    grp = (df_wrong
           .groupby(["true", "pred"], dropna=False)
           .size()
           .reset_index(name="枚数"))
    # 並び替え（枚数降順）
    sheetA = grp.sort_values("枚数", ascending=False, kind="stable").reset_index(drop=True)
    # 列名の和名整形
    sheetA = sheetA.rename(columns={"true": "クラス名（true）", "pred": "間違ったクラス名（pred）"})

    # =============== ② SheetB：間違った画像の一覧 ===============
    # 画像.png 列を作成（拡張子を .png に変更しただけのファイル名）
    df_wrong["画像.png"] = df_wrong["fname"].apply(change_ext_to_png)

    # 列のリネーム（ご指定の出力ヘッダに合わせる）
    # index は出力時に DataFrame の index を使う（1始まりにしたい場合は +1 して列化）
    sheetB = pd.DataFrame({
        "画像名（fname）": df_wrong["fname"].astype(str),
        "画像.png": df_wrong["画像.png"].astype(str),
        "ラベル名（クラス名:true）": df_wrong["true"].astype(str),
        "推論結果（間違い:pred）": df_wrong["pred"].astype(str),
        "top1_pred": pd.to_numeric(df_wrong["pred_score"], errors="coerce"),
        "top2_class": df_wrong["pred_top2"].astype(str),
        "top2_pred": pd.to_numeric(df_wrong["pred_top2_score"], errors="coerce"),
    })
    # 見やすさのため index を 1 始まりの列として付与
    sheetB.insert(0, "index", range(1, len(sheetB) + 1))

    # =============== Excel へ書き出し ===============
    # 既存ブックを維持しつつ追記（同名シートがある場合は置き換え）
    with pd.ExcelWriter(out_path, engine="openpyxl", mode="a", if_sheet_exists="replace") as w:
        sheetA.to_excel(w, sheet_name=args.sheetA_name, index=False)
        sheetB.to_excel(w, sheet_name=args.sheetB_name, index=False)

    print(f"出力完了: {out_path}")
    print(f" - {args.sheetA_name}: 間違いペア（true, pred, 枚数）")
    print(f" - {args.sheetB_name}: 間違い画像一覧")

if __name__ == "__main__":
    main()

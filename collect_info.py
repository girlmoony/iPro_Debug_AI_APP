import pandas as pd
import numpy as np
import re

# ========= 1) 読み込み =========
# Excelの場合
df = pd.read_excel("your_file.xlsx")   # CSVなら pd.read_csv("your_file.csv")

# ========= 2) 列名の正規化（全角・空白・表記ゆれ対策） =========
def norm(col):
    c = str(col).strip()
    c = c.replace("　", " ")          # 全角スペース→半角
    c = re.sub(r"\s+", "_", c)        # 連続空白→_
    return c

df.columns = [norm(c) for c in df.columns]

# 想定カラム名のマッピング（多少の表記ゆれを吸収）
col_map_candidates = {
    "fname": ["fname", "file_name", "ファイル名"],
    "Correct_label": ["Correct_label", "correct_label", "正しいラベル", "正解ラベル"],
    "pred": ["pred", "top1", "推論ラベル", "pred_top1"],
    "pred_score": ["pred_score", "top1_score"],
    "pred_top2": ["pred_top2", "top2_pred", "top2"],
    "pred_top2_score": ["pred_top2_score", "top2_score"],
    "result_type": ["result_type", "結果種別"],
    "correct": ["correct", "is_correct", "top1_correct"],
    "top2_correct": ["top2_correct", "top21_correct", "top2に正解含む"],
}

resolved = {}
for std, cands in col_map_candidates.items():
    for c in cands:
        if c in df.columns:
            resolved[std] = c
            break

required = ["Correct_label", "result_type", "correct", "top2_correct"]
missing = [k for k in required if k not in resolved]
if missing:
    raise ValueError(f"必要な列が見つかりませんでした: {missing}\n現在の列: {list(df.columns)}")

# 以降は標準化名で参照
CL = resolved["Correct_label"]
RT = resolved["result_type"]
C1 = resolved["correct"]
C2 = resolved["top2_correct"]

# ========= 3) ブール列の正規化（1/0, 'true'/'false' 等をTrue/Falseに） =========
def to_bool(s):
    if pd.api.types.is_bool_dtype(df[s]):
        return
    df[s] = df[s].map(lambda x: str(x).strip().lower() if pd.notna(x) else x)
    true_set = {"true", "1", "t", "y", "yes"}
    false_set = {"false", "0", "f", "n", "no"}
    def cast(v):
        if pd.isna(v): return False
        if v in true_set: return True
        if v in false_set: return False
        # 数値文字列なら閾値>0でTrue
        try:
            return float(v) > 0
        except:
            return bool(v)
    df[s] = df[s].map(cast)

to_bool(C1)
to_bool(C2)

# ========= 4) 基本集計（クラスごと） =========
# トータル件数
total_by_class = df.groupby(CL).size().rename("total")

# top1正解数
top1_correct_by_class = df.groupby(CL)[C1].sum(min_count=1).rename("top1_correct").fillna(0).astype(int)

# top2正解数
top2_correct_by_class = df.groupby(CL)[C2].sum(min_count=1).rename("top2_correct").fillna(0).astype(int)

# result_type 別カウント（必要カテゴリのみ抽出）
wanted_types = ["top1正解", "top2正解", "top1誤出発", "top2誤出発", "top2手動"]
rt_pivot = (
    df.pivot_table(index=CL, columns=RT, values=RT, aggfunc="count", fill_value=0)
    .reindex(columns=wanted_types, fill_value=0)
)
# 中でも要求された3つのみを使用
top1_mis = rt_pivot.get("top1誤出発", pd.Series(0, index=rt_pivot.index)).rename("top1誤出発")
top2_mis = rt_pivot.get("top2誤出発", pd.Series(0, index=rt_pivot.index)).rename("top2誤出発")
top2_man = rt_pivot.get("top2手動",   pd.Series(0, index=rt_pivot.index)).rename("top2手動")

# ========= 5) 結合 =========
summary = (
    pd.concat([total_by_class, top1_correct_by_class, top2_correct_by_class, top1_mis, top2_mis, top2_man], axis=1)
    .fillna(0)
    .astype({"total": int, "top1_correct": int, "top2_correct": int, "top1誤出発": int, "top2誤出発": int, "top2手動": int})
)

# ========= 6) クラス番号順にソート（"0001_xxxx" 形式を想定） =========
def class_key(s):
    # 先頭の4桁数値を抽出して数値化、なければ大きめの値
    m = re.match(r"^(\d{1,6})[_-]", str(s))
    if m:
        return (int(m.group(1)), str(s))
    return (10**9, str(s))

summary = summary.sort_values(by=summary.index.to_series().map(class_key))

# ========= 7) 出力 =========
print(summary.head())          # 先頭プレビュー
summary.to_excel("class_summary.xlsx")   # Excelに保存
# summary.to_csv("class_summary.csv", encoding="utf-8-sig")  # CSVが良ければこちら


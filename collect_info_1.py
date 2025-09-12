import pandas as pd
import numpy as np
import re

# ========= 1) 読み込み =========
df = pd.read_excel("your_file.xlsx")   # CSVなら pd.read_csv("your_file.csv")

# ========= 2) 列名の正規化（全角・空白・改行対策） =========
def norm(col):
    c = str(col).replace("\n", " ").replace("\r", " ")
    c = c.strip().replace("　", " ")
    c = re.sub(r"\s+", "_", c)
    return c

df.columns = [norm(c) for c in df.columns]

# 重複列名の簡易検査（重複があると後工程で不安定）
if df.columns.duplicated().any():
    # 重複列がある場合は一意化（例：result_type, result_type_1 ...）
    counts = {}
    new_cols = []
    for c in df.columns:
        if c not in counts:
            counts[c] = 0
            new_cols.append(c)
        else:
            counts[c] += 1
            new_cols.append(f"{c}_{counts[c]}")
    df.columns = new_cols

# ========= 3) 想定カラム名のマッピング =========
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

CL = resolved["Correct_label"]
RT = resolved["result_type"]
C1 = resolved["correct"]
C2 = resolved["top2_correct"]

# ========= 4) 値の正規化 =========
# result_type の空白・全角を正規化
df[RT] = (
    df[RT]
    .astype(str)
    .str.replace("\n", " ", regex=False)
    .str.replace("\r", " ", regex=False)
    .str.replace("　", " ", regex=False)
    .str.strip()
)

# correct / top2_correct をブール化
def to_bool(series_name):
    if pd.api.types.is_bool_dtype(df[series_name]): 
        return
    true_set = {"true","1","t","y","yes","True","TRUE"}
    false_set = {"false","0","f","n","no","False","FALSE"}
    def cast(x):
        if pd.isna(x): return False
        s = str(x).strip()
        if s in true_set: return True
        if s in false_set: return False
        try: return float(s) > 0
        except: return bool(s)
    df[series_name] = df[series_name].map(cast)

to_bool(C1)
to_bool(C2)

# ========= 5) 基本集計 =========
# トータル件数
total_by_class = df.groupby(CL).size().rename("total")

# top1正解数 / top2正解数
top1_correct_by_class = df.groupby(CL)[C1].sum(min_count=1).rename("top1_correct").fillna(0).astype(int)
top2_correct_by_class = df.groupby(CL)[C2].sum(min_count=1).rename("top2_correct").fillna(0).astype(int)

# result_type の種類別カウント（crosstabで安定）
rt_ct = pd.crosstab(df[CL], df[RT])  # index: クラス, columns: 結果種別
wanted_types = ["top1正解", "top2正解", "top1誤出発", "top2誤出発", "top2手動"]
# 欲しい列が無い場合にも0で埋める
rt_ct = rt_ct.reindex(columns=wanted_types, fill_value=0)

top1_mis = rt_ct["top1誤出発"].rename("top1誤出発")
top2_mis = rt_ct["top2誤出発"].rename("top2誤出発")
top2_man = rt_ct["top2手動"].rename("top2手動")

# ========= 6) 結合 =========
summary = (
    pd.concat([total_by_class, top1_correct_by_class, top2_correct_by_class,
               top1_mis, top2_mis, top2_man], axis=1)
    .fillna(0)
    .astype({"total": int, "top1_correct": int, "top2_correct": int,
             "top1誤出発": int, "top2誤出発": int, "top2手動": int})
)

# ========= 7) クラス番号順ソート（"0001_xxxx" 形式を想定） =========
def class_key(s):
    m = re.match(r"^(\d{1,6})[_-]", str(s))
    return (int(m.group(1)) if m else 10**9, str(s))

summary = summary.sort_values(by=summary.index.to_series().map(class_key))

# ========= 8) 出力 =========
print(summary.head())
summary.to_excel("class_summary.xlsx")
# summary.to_csv("class_summary.csv", encoding="utf-8-sig")

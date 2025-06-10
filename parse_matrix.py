import pandas as pd
from openpyxl import load_workbook

# Excelから混同行列を読み込む
matrix_file = "matrix.xlsx"
df = pd.read_excel(matrix_file, sheet_name="matrix", index_col=0)

# 誤認識ペアを抽出（対角線以外で値が0より大きい）
mistakes = []

for true_class in df.index:
    for pred_class in df.columns:
        if true_class != pred_class:
            count = df.at[true_class, pred_class]
            if count > 0:
                mistakes.append({
                    "true_class": true_class,
                    "predicted_class": pred_class,
                    "count": count,
                    "label": f"{true_class}_{pred_class}"
                })

# 多い順にソート
mistakes_df = pd.DataFrame(mistakes).sort_values(by="count", ascending=False)

# Excelに新しいシートとして出力
with pd.ExcelWriter(matrix_file, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
    mistakes_df.to_excel(writer, sheet_name="confused_pairs", index=False)

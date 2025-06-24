import pandas as pd

# ファイル名
excel_file = 'confusedpairsデータ.xlsx'

# シート読み込み
gpu_df = pd.read_excel(excel_file, sheet_name='gpu_confusedpairs')
ipro_df = pd.read_excel(excel_file, sheet_name='ipro_confusedpairs')

# GPUデータ整形
gpu_summary = gpu_df.groupby(['True_label', 'prediction_label'], as_index=False)['枚数'].sum()
gpu_summary.rename(columns={'枚数': 'GPU誤認枚数'}, inplace=True)

# IPROデータ整形
ipro_summary = ipro_df.groupby(['True_label', 'prediction_label'], as_index=False)['枚数'].sum()
ipro_summary.rename(columns={'枚数': 'IPRO誤認枚数'}, inplace=True)

# 両方結合
merged = pd.merge(gpu_summary, ipro_summary, how='outer', on=['True_label', 'prediction_label'])

# NaNを0に置き換え
merged['GPU誤認枚数'] = merged['GPU誤認枚数'].fillna(0).astype(int)
merged['IPRO誤認枚数'] = merged['IPRO誤認枚数'].fillna(0).astype(int)

# 差分画像数（IPROのみ間違い）計算
merged['差分画像数（IPROのみ）'] = merged['IPRO誤認枚数'] - merged['GPU誤認枚数']
merged['差分画像数（IPROのみ）'] = merged['差分画像数（IPROのみ）'].apply(lambda x: x if x > 0 else 0)

# 誤認リストリンク列作成（True_label名をファイル名にする想定）
merged['誤認リストリンク'] = merged['True_label'].astype(str) + '.xlsx'

# 列名整理
merged.rename(columns={
    'True_label': 'クラス名',
    'prediction_label': '誤認識ペア'
}, inplace=True)

# 結果確認
print(merged[['クラス名', '誤認識ペア', 'GPU誤認枚数', 'IPRO誤認枚数', '差分画像数（IPROのみ）', '誤認リストリンク']].head())

# 必要ならエクセル出力
with pd.ExcelWriter(excel_file, mode='a', engine='openpyxl', if_sheet_exists='replace') as writer:
    merged.to_excel(writer, sheet_name='誤認識ペア集計', index=False)

print('誤認識ペア集計シートを同じExcel内に追加しました。')

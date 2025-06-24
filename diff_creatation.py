import pandas as pd
from openpyxl import load_workbook

# ファイル名（必要に応じてパスを変更）
excel_file = '判定結果まとめ.xlsx'

# シート読み込み
ipro_df = pd.read_excel(excel_file, sheet_name='IPROログ')
gpu_wrong_df = pd.read_excel(excel_file, sheet_name='GPU誤認識')

# GPUの予測ラベルをマッピング辞書化
gpu_pred_dict = dict(zip(gpu_wrong_df['画像名'], gpu_wrong_df['prediction-label']))

# GPU-label列：GPU予測ラベル（間違っていない場合はtrue-labelとする）
ipro_df['GPU-label'] = ipro_df.apply(
    lambda row: gpu_pred_dict[row['画像名']] if row['画像名'] in gpu_pred_dict else row['true-label'],
    axis=1
)

# IPRO-label列：IPROの予測ラベル（top1-labelそのまま）
ipro_df['IPRO-label'] = ipro_df['top1-label']

# 判定結果列
ipro_df['判定結果'] = ipro_df.apply(
    lambda row: ('×' if row['GPU-label'] != row['true-label'] else '○') + ' / ' +
                ('×' if row['IPRO-label'] != row['true-label'] else '○'),
    axis=1
)

# 備考列
def 備考判定(row):
    gpu_ng = row['GPU-label'] != row['true-label']
    ipro_ng = row['IPRO-label'] != row['true-label']
    if gpu_ng and ipro_ng:
        return '両方NG'
    elif not gpu_ng and ipro_ng:
        return '差分対象'
    else:
        return ''

ipro_df['備考'] = ipro_df.apply(備考判定, axis=1)

# 出力する列だけ抽出
output_df = ipro_df[['画像名', 'true-label', 'GPU-label', 'IPRO-label', '判定結果', '備考']]

# 同じファイルに新規シートとして保存
with pd.ExcelWriter(excel_file, mode='a', engine='openpyxl', if_sheet_exists='replace') as writer:
    output_df.to_excel(writer, sheet_name='判定結果', index=False)

print('同じExcel内の「判定結果」シートに保存しました。')

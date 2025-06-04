import pandas as pd
import numpy as np
from PIL import Image
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XLImage
from openpyxl.utils.dataframe import dataframe_to_rows
import os
import io

# -------------------------------
# RAW画像仕様（必要に応じて変更）
# -------------------------------
width = 224       # 画像幅
height = 224      # 画像高さ
channels = 1      # グレースケール=1、RGB=3

# -------------------------------
# Excelファイルの読み込み
# -------------------------------
input_path = "input.xlsx"
q_sheet = pd.read_excel(input_path, sheet_name="Q")
b_sheet = pd.read_excel(input_path, sheet_name="B")

# -------------------------------
# Qシート290行目から処理
# -------------------------------
results = []

for idx in range(289, len(q_sheet)):  # Excelの290行目から
    entry = q_sheet.loc[idx, 'A']
    if not isinstance(entry, str) or "_" not in entry:
        continue

    parts = entry.split('_')
    if len(parts) < 4:
        continue

    true_class = f"{parts[0]}_{parts[1]}"
    pred_class = f"{parts[2]}_{parts[3]}"

    matches = b_sheet[(b_sheet['True'] == true_class) & (b_sheet['Pred'] == pred_class)]

    for _, row in matches.iterrows():
        raw_file = row['RawFile']
        image_path = os.path.join("Wrong images", true_class, raw_file)
        results.append({
            'index': len(results),
            'classname': true_class,
            'imagename': raw_file,
            'image_path': image_path
        })

# -------------------------------
# Excelのワークブックに result シート追加
# -------------------------------
wb = load_workbook(input_path)
if 'result' in wb.sheetnames:
    del wb['result']
ws = wb.create_sheet(title='result')
ws.append(['index', 'classname', 'imagename', 'image'])

# -------------------------------
# 結果を1行ずつ貼り付け＋画像処理
# -------------------------------
for row in results:
    r = ws.max_row + 1
    ws.cell(row=r, column=1, value=row['index'])
    ws.cell(row=r, column=2, value=row['classname'])
    ws.cell(row=r, column=3, value=row['imagename'])

    raw_path = row['image_path']
    if os.path.exists(raw_path):
        with open(raw_path, 'rb') as f:
            raw_data = f.read()
            img_array = np.frombuffer(raw_data, dtype=np.uint8)
            if len(img_array) == width * height * channels:
                if channels == 1:
                    img_array = img_array.reshape((height, width))
                    pil_img = Image.fromarray(img_array, 'L')
                else:
                    img_array = img_array.reshape((height, width, channels))
                    pil_img = Image.fromarray(img_array, 'RGB')

                img_io = io.BytesIO()
                pil_img.save(img_io, format='PNG')
                img_io.seek(0)
                xl_img = XLImage(img_io)
                ws.add_image(xl_img, f'D{r}')

# -------------------------------
# 上書き保存
# -------------------------------
wb.save(input_path)
print("✅ 完了: 結果を input.xlsx の result シートに保存しました。")


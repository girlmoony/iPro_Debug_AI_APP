import cv2
import os
from PIL import Image
import numpy as np
import pandas as pd

def is_blurry(image_path, threshold=100.0):
    img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None, None  # 読み込み失敗
    laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
    is_blur = laplacian_var < threshold
    return laplacian_var, is_blur

# フォルダ内の画像をチェック
folder_path = "your_folder_of_images"  # ← 実際の画像フォルダパスに変更
threshold = 100.0
blurry_count = 0
total = 0
results = []

for filename in os.listdir(folder_path):
    if filename.lower().endswith((".jpg", ".jpeg", ".png")):
        total += 1
        path = os.path.join(folder_path, filename)
        blur_score, is_blur = is_blurry(path, threshold=threshold)
        if blur_score is not None:
            if is_blur:
                blurry_count += 1
            results.append({
                "image_name": filename,
                "image_path": path,
                "blur_score": blur_score,
                "is_blurry": is_blur
            })

# 結果をExcelに保存
df = pd.DataFrame(results)
output_excel = os.path.join(folder_path, "blur_check_results.xlsx")
df.to_excel(output_excel, index=False)

# 結果を表示
print(f"ぼやけ画像数: {blurry_count}/{total}（{100 * blurry_count / total:.2f}%）")
print(f"結果をExcelに保存しました: {output_excel}")



import cv2
import os
import pandas as pd

def is_blurry(image_path, threshold=100.0):
    # 日本語パス対応：OpenCVでは直接読めないため numpy 経由
    with open(image_path, 'rb') as f:
        img_array = np.asarray(bytearray(f.read()), dtype=np.uint8)
        img = cv2.imdecode(img_array, cv2.IMREAD_GRAYSCALE)
    if img is None:
        return None, None
    laplacian_var = cv2.Laplacian(img, cv2.CV_64F).var()
    is_blur = laplacian_var < threshold
    return laplacian_var, is_blur

# 画像の親フォルダパス（例： 'C:/data/寿司画像' など）
folder_path = "your_folder_of_images"  # 実パスに変更してください
threshold = 100.0
blurry_count = 0
total = 0
results = []

# サブディレクトリを含めて再帰的に検索
for root, dirs, files in os.walk(folder_path):
    for filename in files:
        if filename.lower().endswith((".jpg", ".jpeg", ".png")):
            total += 1
            path = os.path.join(root, filename)
            blur_score, is_blur = is_blurry(path, threshold=threshold)
            if blur_score is not None:
                if is_blur:
                    blurry_count += 1
                results.append({
                    "class_folder": os.path.basename(root),  # 例: "01_えび"
                    "image_name": filename,
                    "image_path": path,
                    "blur_score": blur_score,
                    "is_blurry": is_blur
                })

# Excel出力
df = pd.DataFrame(results)
output_excel = os.path.join(folder_path, "blur_check_results.xlsx")
df.to_excel(output_excel, index=False)

# 結果表示
print(f"ぼやけ画像数: {blurry_count}/{total}（{100 * blurry_count / total:.2f}%）")
print(f"結果をExcelに保存しました: {output_excel}")


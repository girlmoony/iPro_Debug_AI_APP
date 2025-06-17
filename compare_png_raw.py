import cv2
import numpy as np
import matplotlib.pyplot as plt

def compare_png_and_raw(png_path, raw_path):
    # PNG画像読み込み（学習時と同じ前処理で）
    img_png = cv2.imread(png_path, cv2.IMREAD_COLOR)  # BGR、8bit、3ch

    # RAWデータ読み込み（.tobytes() で保存された前提）
    with open(raw_path, 'rb') as f:
        raw_bytes = f.read()

    # shape, dtypeは PNG に合わせて変換
    raw_array = np.frombuffer(raw_bytes, dtype=img_png.dtype).reshape(img_png.shape)

    # 差分計算
    diff = np.abs(img_png.astype(np.int32) - raw_array.astype(np.int32))
    max_diff = np.max(diff)
    num_diff = np.count_nonzero(diff)

    # 判定出力
    if np.array_equal(img_png, raw_array):
        print("✅ 完全一致：PNGとRAWの画素は同一です。")
    else:
        print("⚠️ 差分あり：")
        print(f"   - 最大画素差: {max_diff}")
        print(f"   - 異なる画素数: {num_diff} / {img_png.size}")

        # 差分の最大値（各ピクセル単位）を強調表示
        diff_map = np.max(diff, axis=2)  # RGBの中で最大の差をピクセルごとに

        plt.figure(figsize=(8, 6))
        plt.imshow(diff_map, cmap='hot')
        plt.title("Pixel Difference Map (Max per pixel)")
        plt.colorbar(label="Pixel Intensity Difference")
        plt.tight_layout()
        plt.show()

# 使用例
compare_png_and_raw("test_image.png", "test_image.raw")

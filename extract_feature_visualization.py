import cv2
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from skimage import color, feature
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
import seaborn as sns
import os

# エクセルから画像パスとラベルを取得
labels_df = pd.read_excel("labels.xlsx", sheet_name="image_details")

# 結果を格納
data = []

# 特徴量計算関数
def extract_features(image_path):
    img = cv2.imread(image_path)
    if img is None:
        print(f"画像読み込み失敗: {image_path}")
        return None

    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

    # 彩度
    saturation = np.mean(img_hsv[:, :, 1])

    # ノイズレベル（ラプラシアンの分散）
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    noise_level = cv2.Laplacian(gray, cv2.CV_64F).var()

    # テクスチャ複雑度（GLCMエネルギー）
    gray_8bit = cv2.resize(gray, (64, 64))
    glcm = feature.greycomatrix(gray_8bit, distances=[1], angles=[0], symmetric=True, normed=True)
    texture_energy = feature.greycoprops(glcm, 'energy')[0, 0]

    # 色温度（青の割合）
    r_mean = np.mean(img_rgb[:, :, 0])
    g_mean = np.mean(img_rgb[:, :, 1])
    b_mean = np.mean(img_rgb[:, :, 2])
    color_temp = b_mean / (r_mean + 1e-5)

    return saturation, noise_level, texture_energy, color_temp

# データ収集
for idx, row in labels_df.iterrows():
    img_path = row["image_path"]
    label = row["label"]

    if not os.path.exists(img_path):
        print(f"ファイルが存在しません: {img_path}")
        continue

    features = extract_features(img_path)
    if features is None:
        continue

    saturation, noise_level, texture_energy, color_temp = features

    data.append({
        "image_path": img_path,
        "saturation": saturation,
        "noise_level": noise_level,
        "texture_energy": texture_energy,
        "color_temp": color_temp,
        "label": label
    })

# DataFrame化
df = pd.DataFrame(data)
print(df.head())

# 可視化例
sns.boxplot(data=df, x="label", y="saturation")
plt.title("Saturation by Label")
plt.show()

sns.boxplot(data=df, x="label", y="noise_level")
plt.title("Noise Level by Label")
plt.show()

sns.boxplot(data=df, x="label", y="texture_energy")
plt.title("Texture Energy by Label")
plt.show()

sns.boxplot(data=df, x="label", y="color_temp")
plt.title("Color Temperature by Label")
plt.show()

# モデル構築
X = df[["saturation", "noise_level", "texture_energy", "color_temp"]]
y = df["label"].map({"正確": 0, "不正確": 1})

X_train, X_test, y_train, y_test = train_test_split(X, y, stratify=y, random_state=42)

model = RandomForestClassifier(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

y_pred = model.predict(X_test)
print(classification_report(y_test, y_pred))

# 重要特徴量
importances = model.feature_importances_
plt.bar(X.columns, importances)
plt.title("Feature Importance")
plt.show()

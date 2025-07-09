import pandas as pd
from scipy.stats import ttest_ind
import seaborn as sns
import matplotlib.pyplot as plt

# ① Excel読み込み
df = pd.read_excel("画像特徴量_all_1000件データ.xlsx")

# ② 構成タイプ列を作成（現行1＋下段など）
df["構成タイプ"] = df["genko"] + df["up_down"]

# ③ 判定ラベル作成（○/○など）
#df["判定"] = df["gpu_result"] + "/" + df["ipro_result"]

# 判定列を使って差分を抽出
df_pos = df[df["判定"] == "○/×"]
df_others = df[df["判定"].isin(["○/○", "×/○"])]

# ④ 分析対象の構成リスト
構成リスト = ["現行1下段", "現行2上段", "現行2下段"]

# ⑤ 特徴量カラム（画像特徴量の列を自動選定、または明示指定）
feature_cols = [col for col in df.columns if col.startswith("feature_")]

# 結果をまとめるリスト
result_all = []

for 構成 in 構成リスト:
    df_sub = df[df["構成タイプ"] == 構成]
    df_pos = df_sub[df_sub["判定"] == "○/×"]
    df_others = df_sub[df_sub["判定"] != "○/×"]

    for col in feature_cols:
        try:
            t_stat, p_val = ttest_ind(df_pos[col], df_others[col], equal_var=False)
            result_all.append({
                "構成タイプ": 構成,
                "特徴量": col,
                "○/×_平均": df_pos[col].mean(),
                "他_平均": df_others[col].mean(),
                "p値": p_val
            })
        except:
            continue

# 結果をデータフレーム化
df_result = pd.DataFrame(result_all)
df_result["有意差あり"] = df_result["p値"] < 0.05

# 可視化（Boxplot）
for 構成 in 構成リスト:
    df_sub = df[df["構成タイプ"] == 構成]
    for col in feature_cols:
        plt.figure(figsize=(6,4))
        sns.boxplot(x="判定", y=col, data=df_sub[df_sub["判定"].isin(["○/×", "○/○", "×/○"])])
        plt.title(f"{構成} - {col}")
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.show()


import pandas as pd
import cv2
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# 画像特徴を抽出する関数
def extract_features(img_path):
    try:
        img = cv2.imread(img_path)
        if img is None:
            return [np.nan]*4  # 読み込み失敗

        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # 明るさ（平均輝度）
        brightness = np.mean(img_gray)

        # ぼやけ（Laplacianの分散）
        blur = cv2.Laplacian(img_gray, cv2.CV_64F).var()

        # コントラスト（標準偏差）
        contrast = np.std(img_gray)

        # 彩度（HSVのS成分の平均）
        saturation = np.mean(img_hsv[:, :, 1])

        return [brightness, blur, contrast, saturation]
    except:
        return [np.nan]*4

# Excel読み込み
df = pd.read_excel("画像特徴量_all_1000件データ.xlsx")

# 構成タイプ列を作成
df["構成タイプ"] = df["genko"] + df["up_down"]

# 特徴量抽出
df[["明るさ", "ぼやけ", "コントラスト", "彩度"]] = df["img_path"].apply(extract_features).apply(pd.Series)

# 分布可視化（Boxplot）
for col in ["明るさ", "ぼやけ", "コントラスト", "彩度"]:
    plt.figure(figsize=(6, 4))
    sns.boxplot(x="構成タイプ", y=col, data=df[df["構成タイプ"].isin(["現行1下段", "現行2上段", "現行2下段"])])
    plt.title(f"{col} の分布（構成タイプ別）")
    plt.tight_layout()
    plt.show()

# 構成別平均も表示
summary = df.groupby("構成タイプ")[["明るさ", "ぼやけ", "コントラスト", "彩度"]].mean()
print(summary)

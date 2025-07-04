import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE

# エクセル読み込み
excel_path = 'your_excel_file.xlsx'  # 実際のファイルパスに置き換え
df = pd.read_excel(excel_path)

# 必要な列だけ抽出
features = df[['R_mean', 'G_mean', 'B_mean', 'Brightness', 'Contrast', 'Sharpness']]

# 既存の「判定結果」列をそのままラベルとして使用
labels = df['判定結果']  # 列名が正確に「判定結果」であることを確認してください

# ---------- PCA 可視化 ----------
pca = PCA(n_components=2)
pca_result = pca.fit_transform(features)

plt.figure(figsize=(7, 6))
for label in labels.unique():
    idx = labels == label
    plt.scatter(pca_result[idx, 0], pca_result[idx, 1], label=label, alpha=0.7)

plt.title('PCAによる可視化')
plt.xlabel('PC1')
plt.ylabel('PC2')
plt.legend()
plt.show()

# ---------- t-SNE 可視化 ----------
tsne = TSNE(n_components=2, random_state=0, perplexity=30, n_iter=1000)
tsne_result = tsne.fit_transform(features)

plt.figure(figsize=(7, 6))
for label in labels.unique():
    idx = labels == label
    plt.scatter(tsne_result[idx, 0], tsne_result[idx, 1], label=label, alpha=0.7)

plt.title('t-SNEによる可視化')
plt.xlabel('Dim 1')
plt.ylabel('Dim 2')
plt.legend()
plt.show()

#for all
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
import seaborn as sns
import matplotlib.pyplot as plt

# 特徴量リスト（必要に応じて拡張）
feature_list = ["saturation", "noise_level", "texture_energy", "color_temp"]

# 特徴量だけ抽出
X = df[feature_list].values
labels = df["true_label"].values  # 20クラス用

# PCA 2次元
pca = PCA(n_components=2)
X_pca = pca.fit_transform(X)

plt.figure(figsize=(6, 6))
sns.scatterplot(x=X_pca[:, 0], y=X_pca[:, 1], hue=labels, palette="tab20", legend="full")
plt.title("PCA 全クラス可視化")
plt.show()

# t-SNE 2次元
tsne = TSNE(n_components=2, random_state=42, perplexity=30)
X_tsne = tsne.fit_transform(X)

plt.figure(figsize=(6, 6))
sns.scatterplot(x=X_tsne[:, 0], y=X_tsne[:, 1], hue=labels, palette="tab20", legend="full")
plt.title("t-SNE 全クラス可視化")
plt.show()

for true_label in df["true_label"].unique():
    sub_df = df[df["true_label"] == true_label]

    X_sub = sub_df[feature_list].values
    sub_labels = sub_df["label"].values  # 判定結果（〇/〇、×/×など）

    # PCA
    pca = PCA(n_components=2)
    X_pca = pca.fit_transform(X_sub)

    plt.figure(figsize=(6, 6))
    sns.scatterplot(x=X_pca[:, 0], y=X_pca[:, 1], hue=sub_labels, palette="Set2")
    plt.title(f"PCA - {true_label} クラス内")
    plt.show()

    # t-SNE
    tsne = TSNE(n_components=2, random_state=42, perplexity=30)
    X_tsne = tsne.fit_transform(X_sub)

    plt.figure(figsize=(6, 6))
    sns.scatterplot(x=X_tsne[:, 0], y=X_tsne[:, 1], hue=sub_labels, palette="Set2")
    plt.title(f"t-SNE - {true_label} クラス内")
    plt.show()

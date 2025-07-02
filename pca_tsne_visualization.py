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

import pandas as pd
import numpy as np
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans

# データ読み込み・特徴量・ラベル準備（既存コード前提）
features = df[['R_mean', 'G_mean', 'B_mean', 'Brightness', 'Contrast', 'Sharpness']]
labels = df['判定結果']

# t-SNE
tsne_result = TSNE(n_components=2, random_state=0, perplexity=30).fit_transform(features)

# KMeansクラスタリング（クラスタ数は適宜調整）
kmeans = KMeans(n_clusters=5, random_state=0)
cluster_labels = kmeans.fit_predict(tsne_result)

df['クラスタ'] = cluster_labels

# 誤判定とみなす条件（ここは状況に応じて変更）
誤判定条件 = (labels == '〇/×') | (labels == '×/〇')
df['誤判定'] = 誤判定条件

# クラスタごとの誤判定率集計
結果 = df.groupby('クラスタ')['誤判定'].agg(['count', 'sum'])
結果['誤判定率'] = 結果['sum'] / 結果['count']

print(結果)

 クラスタごとに特徴量分布を可視化するコード
import seaborn as sns
import matplotlib.pyplot as plt

# 例：Brightnessのクラスタごとの分布
plt.figure(figsize=(10, 6))
sns.boxplot(data=df, x='クラスタ', y='Brightness')
plt.title('Brightnessのクラスタごとの分布')
plt.show()

# 例：R_meanのクラスタごとの分布
plt.figure(figsize=(10, 6))
sns.boxplot(data=df, x='クラスタ', y='R_mean')
plt.title('R_meanのクラスタごとの分布')
plt.show()

境界領域を数値的に把握する方法の提案
from scipy.spatial.distance import cdist

# 各クラスタの中心
centroids = kmeans.cluster_centers_

# 各データ点と自クラスタ中心の距離計算
df['クラスタ中心距離'] = [
    np.linalg.norm(tsne_result[i] - centroids[cluster_labels[i]])
    for i in range(len(df))
]

# 距離が大きいデータを確認
print(df.sort_values('クラスタ中心距離', ascending=False).head())


import seaborn as sns
import matplotlib.pyplot as plt

# 対象の特徴量リスト
特徴量リスト = ['R_mean', 'G_mean', 'B_mean', 'Brightness', 'Contrast', 'Sharpness']

# 各特徴量ごとにクラスタ別のボックスプロットを表示
for 特徴量 in 特徴量リスト:
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='クラスタ', y=特徴量)
    plt.title(f'{特徴量} のクラスタごとの分布')
    plt.show()


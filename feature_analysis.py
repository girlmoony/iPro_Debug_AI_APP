
import os
import cv2
import numpy as np
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
from glob import glob

def extract_features(image_path):
    img = cv2.imread(image_path)
    if img is None:
        return None
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    mean_brightness = np.mean(gray)
    std_brightness = np.std(gray)
    edges = cv2.Canny(gray, 100, 200)
    edge_density = np.sum(edges) / (h * w)
    return [mean_brightness, std_brightness, edge_density, h, w]

def collect_image_paths(base_dir):
    class_dict = {}
    for class_dir in os.listdir(base_dir):
        path = os.path.join(base_dir, class_dir)
        if not os.path.isdir(path):
            continue
        class_dict[class_dir] = {
            'TP': glob(os.path.join(path, 'TP', '*.jpg')),
            'FN': glob(os.path.join(path, 'FN', '*.jpg')),
        }
    return class_dict

def visualize_tsne(features, labels):
    tsne = TSNE(n_components=2, random_state=42)
    features_2d = tsne.fit_transform(features)
    plt.figure(figsize=(10, 6))
    for label in set(labels):
        idx = [i for i, l in enumerate(labels) if l == label]
        plt.scatter(features_2d[idx, 0], features_2d[idx, 1], label=label, alpha=0.7)
    plt.title('t-SNE Visualization of TP vs FN Features')
    plt.xlabel('Component 1')
    plt.ylabel('Component 2')
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    image_dict = collect_image_paths("data/")
    features = []
    labels = []
    for class_id, paths in image_dict.items():
        for kind in ['TP', 'FN']:
            for path in paths[kind]:
                feat = extract_features(path)
                if feat:
                    features.append(feat)
                    labels.append(f"{class_id}_{kind}")
    visualize_tsne(features, labels)


import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import ttest_ind

# データ読み込み
判定_df = pd.read_excel('判定結果まとめ.xlsx', sheet_name='判定結果')
特徴量_df = pd.read_excel('画像特徴量.xlsx', sheet_name='特徴量')

# 画像名を整える（必要なら）
特徴量_df['画像名_clean'] = 特徴量_df['画像名'].str.replace('.raw', '').str.replace('.png', '')
判定_df['画像名_clean'] = 判定_df['画像名'].str.replace('.raw', '').str.replace('.png', '')

# 結合
merged_df = pd.merge(判定_df, 特徴量_df, on='画像名_clean', how='inner')

# 結果保存リスト
結果 = []

# クラスごとに処理
for true_class in merged_df['true_label'].unique():
    df_class = merged_df[merged_df['true_label'] == true_class]
    
    正常_df = df_class[df_class['判定結果'] == '○ / ○']
    間違_df = df_class[df_class['備考'] == '差分対象']
    
    if 正常_df.empty or 間違_df.empty:
        continue  # データ不足ならスキップ
    
    for col in ['平均色R', '平均色G', '平均色B', '輝度平均', 'コントラスト', '鮮明度', '構図スコア']:
        正常値 = 正常_df[col].dropna()
        間違値 = 間違_df[col].dropna()
        
        if len(正常値) > 2 and len(間違値) > 2:
            正常平均 = 正常値.mean()
            正常_std = 正常値.std()
            間違平均 = 間違値.mean()
            
            t_stat, p_val = ttest_ind(正常値, 間違値, equal_var=False)
            
            結果.append({
                'クラス': true_class,
                '特徴量': col,
                '正常平均': 正常平均,
                '正常STD': 正常_std,
                '間違平均': 間違平均,
                't値': t_stat,
                'p値': p_val
            })
            
            # 差が顕著なら分布をプロット
            if p_val < 0.05:
                plt.figure()
                plt.hist(正常値, bins=15, alpha=0.5, label='正しい画像')
                plt.hist(間違値, bins=15, alpha=0.5, label='間違った画像')
                plt.title(f'クラス:{true_class} 特徴量:{col} 分布比較 (p={p_val:.3f})')
                plt.legend()
                plt.show()

# 結果表示
結果_df = pd.DataFrame(結果).sort_values('p値')
print(結果_df)


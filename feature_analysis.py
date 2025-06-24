
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


import cv2
import numpy as np
import pandas as pd
import os
import matplotlib.pyplot as plt
from scipy.stats import ttest_ind

# ==========================
# 設定
# ==========================
画像フォルダ = '画像フォルダのパス'  # 実際の画像パスを指定
判定ファイル = '判定結果まとめ.xlsx'
特徴量出力ファイル = '画像特徴量.xlsx'
比較結果ファイル = '特徴量_比較結果_〇×_vs_その他.xlsx'

import os
import pandas as pd

画像フォルダ = '画像フォルダのパス'
判定ファイル = '判定結果まとめ.xlsx'

# 差分大きい20クラスのリスト取得
差分クラス_df = pd.read_excel(判定ファイル, sheet_name='誤認識ペア一覧')  # 20クラスが入ったシート名に合わせる
差分クラス = 差分クラス_df['クラス名'].unique()

print("差分大きい20クラス：", 差分クラス)

# 該当クラスの画像パス収集
対象画像パス = []
for クラス名 in 差分クラス:
    クラスフォルダ = os.path.join(画像フォルダ, クラス名)
    if os.path.isdir(クラスフォルダ):
        for img in os.listdir(クラスフォルダ):
            if img.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.raw')):
                対象画像パス.append(os.path.join(クラスフォルダ, img))
    else:
        print(f"※ フォルダが見つかりません: {クラスフォルダ}")

print(f"抽出対象の画像数：{len(対象画像パス)}")


# ==========================
# ① 画像特徴量抽出
# ==========================
print("画像特徴量抽出中...")

結果リスト = []
画像リスト = [f for f in os.listdir(画像フォルダ) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.raw'))]

for img_name in 画像リスト:
    img_path = os.path.join(画像フォルダ, img_name)
    img = cv2.imread(img_path)
    if img is None:
        continue

    mean_color = img.mean(axis=(0, 1))
    mean_b, mean_g, mean_r = mean_color
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    brightness_mean = gray.mean()
    contrast_std = gray.std()
    sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
    h, w = gray.shape
    aspect_ratio = w / h

    結果リスト.append({
        '画像名': img_name,
        '平均色R': mean_r,
        '平均色G': mean_g,
        '平均色B': mean_b,
        '輝度平均': brightness_mean,
        'コントラスト': contrast_std,
        '鮮明度': sharpness,
        '構図スコア': aspect_ratio
    })

特徴量_df = pd.DataFrame(結果リスト)
特徴量_df['画像名_clean'] = 特徴量_df['画像名'].str.replace('.raw', '').str.replace('.png', '', regex=False)
特徴量_df.to_excel(特徴量出力ファイル, index=False)
print(f"画像特徴量を {特徴量出力ファイル} に保存しました。")

# ==========================
# ② 判定結果読み込み＆結合
# ==========================
判定_df = pd.read_excel(判定ファイル, sheet_name='判定結果')
判定_df['画像名_clean'] = 判定_df['画像名'].str.replace('.raw', '').str.replace('.png', '', regex=False)
merged_df = pd.merge(判定_df, 特徴量_df, on='画像名_clean', how='inner')

# 判定種別列（×/×だけ除外）
def 判定区分(row):
    if row['判定結果'].strip() == '〇 / ×':
        return '差分対象'
    elif row['判定結果'].strip() == '× / ×':
        return '除外'
    else:
        return '比較対象'

merged_df['判定区分'] = merged_df.apply(判定区分, axis=1)
merged_df = merged_df[merged_df['判定区分'] != '除外']  # ×/×除外

# ==========================
# ③ クラスごとに比較＆しきい値抽出
# ==========================
print("クラスごとに特徴量比較＆しきい値抽出...")

結果 = []

for true_class in merged_df['true_label'].unique():
    df_class = merged_df[merged_df['true_label'] == true_class]
    差分_df = df_class[df_class['判定区分'] == '差分対象']
    比較_df = df_class[df_class['判定区分'] == '比較対象']
    
    if 差分_df.empty or 比較_df.empty:
        continue
    
    for col in ['平均色R', '平均色G', '平均色B', '輝度平均', 'コントラスト', '鮮明度', '構図スコア']:
        差分値 = 差分_df[col].dropna()
        比較値 = 比較_df[col].dropna()
        
        if len(差分値) > 2 and len(比較値) > 2:
            差分平均 = 差分値.mean()
            比較平均 = 比較値.mean()
            
            t_stat, p_val = ttest_ind(差分値, 比較値, equal_var=False)
            
            # しきい値候補（比較対象の平均 ± 1標準偏差）
            比較_std = 比較値.std()
            上限 = 比較平均 + 比較_std
            下限 = 比較平均 - 比較_std

            結果.append({
                'クラス': true_class,
                '特徴量': col,
                '差分対象平均': 差分平均,
                '比較対象平均': 比較平均,
                '比較対象STD': 比較_std,
                'しきい値下限': 下限,
                'しきい値上限': 上限,
                't値': t_stat,
                'p値': p_val
            })
            
            if p_val < 0.05:
                plt.figure()
                plt.hist(差分値, bins=15, alpha=0.5, label='〇 / × (差分対象)')
                plt.hist(比較値, bins=15, alpha=0.5, label='その他')
                plt.axvline(下限, color='black', linestyle='dashed', label='しきい値下限')
                plt.axvline(上限, color='black', linestyle='dashed', label='しきい値上限')
                plt.title(f'クラス:{true_class} 特徴量:{col} 分布比較 (p={p_val:.3f})')
                plt.legend()
                plt.show()

# ==========================
# ④ 結果出力
# ==========================
結果_df = pd.DataFrame(結果).sort_values('p値')
結果_df.to_excel(比較結果ファイル, index=False)
print(f"特徴量比較結果としきい値を {比較結果ファイル} に保存しました。")



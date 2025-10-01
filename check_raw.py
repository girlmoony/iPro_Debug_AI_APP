import numpy as np
from pathlib import Path

def load_raw_two_ways(raw_path, H, W, C, dtype):
    """
    raw_path: .rawファイルパス
    H, W, C: 画像サイズ（高さ, 幅, チャンネル）
    dtype   : numpyのdtype文字列 ('uint8', 'uint16', 'float32' など)

    戻り値:
      img_A: 仮説A（パターン①）で復元した HxWxC の配列
      img_B: 仮説B（パターン②）で復元した HxWxC の配列
    """
    buf = np.fromfile(raw_path, dtype=dtype)
    expected = H * W * C
    if buf.size != expected:
        raise ValueError(f"サイズ不一致: 期待={expected} 要素, 実際={buf.size} 要素")

    # 仮説A（パターン①）:
    #   元は HxWxC を order='F' で直列化
    #   これは CxWxH を C順で直列化したものと等価
    #   → 読む側は (C, W, H) にreshape → (H, W, C)へ転置
    img_A = buf.reshape((C, W, H)).transpose(2, 1, 0)

    # 仮説B（パターン②）:
    #   元は (C, H, W) を C順で直列化（= HxWxC を transpose(2,0,1)後に直列化）
    #   → 読む側は (C, H, W) にreshape → (H, W, C)へ転置
    img_B = buf.reshape((C, H, W)).transpose(1, 2, 0)

    return img_A, img_B

def total_variation_score(img):
    """
    HxWxC の画像に対して、隣接画素の絶対差の平均（横+縦）を返す。
    値が小さいほど“自然な”画像になりやすい。
    """
    x = img.astype(np.float32)
    # 横方向差分
    dx = np.abs(np.diff(x, axis=1)).mean()
    # 縦方向差分
    dy = np.abs(np.diff(x, axis=0)).mean()
    return float(dx + dy)

def guess_pattern(raw_path, H, W, C, dtype='uint8'):
    img_A, img_B = load_raw_two_ways(raw_path, H, W, C, dtype)
    score_A = total_variation_score(img_A)
    score_B = total_variation_score(img_B)

    if score_A < score_B:
        guess = "パターン①（order='F'）"
        chosen = img_A
    else:
        guess = "パターン②（transpose(2,0,1)→order='C'）"
        chosen = img_B

    return {
        "guess": guess,
        "score_A": score_A,
        "score_B": score_B,
        "img_A": img_A,  # 必要なら可視化や保存に使用
        "img_B": img_B,
        "chosen_img": chosen
    }

# 使い方例:
# result = guess_pattern("path/to/image.raw", H=1080, W=1920, C=3, dtype='uint8')
# print(result["guess"], result["score_A"], result["score_B"])
# 画像として確認したい場合:
# from imageio.v3 import imwrite
# imwrite("hypA.png", result["img_A"])
# imwrite("hypB.png", result["img_B"])

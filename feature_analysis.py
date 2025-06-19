
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

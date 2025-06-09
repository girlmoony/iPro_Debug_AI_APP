import os
import torch
from torchvision import transforms
from PIL import Image
from tqdm import tqdm
from transformers import CLIPProcessor, CLIPModel
import numpy as np
from collections import defaultdict
import shutil

# 参数配置
DATASET_DIR = "train_dataset"  # 数据集目录（所有图片）
OUTPUT_DIR = "calibration_dataset"  # 输出筛选后的图片
NUM_SELECT = 3  # 每类保留图片数量

# 加载模型
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32").to(device)
processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# 图像预处理
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])

# 获取类别 → 图片路径列表
class_to_images = defaultdict(list)
for fname in os.listdir(DATASET_DIR):
    if fname.lower().endswith((".jpg", ".png", ".jpeg")):
        label = fname.split("_")[0]
        class_to_images[label].append(os.path.join(DATASET_DIR, fname))

os.makedirs(OUTPUT_DIR, exist_ok=True)

# 主循环
for label, image_paths in tqdm(class_to_images.items(), desc="Processing classes"):
    features = []

    # 提取每张图片的特征
    for path in image_paths:
        image = Image.open(path).convert("RGB")
        inputs = processor(images=image, return_tensors="pt", padding=True).to(device)
        with torch.no_grad():
            feature = model.get_image_features(**inputs)
            feature = feature / feature.norm(dim=-1, keepdim=True)
            features.append((path, feature.cpu().numpy()[0]))

    # 计算距离矩阵
    feature_matrix = np.stack([f[1] for f in features])
    similarity = feature_matrix @ feature_matrix.T  # cosine similarity
    diversity_score = 1 - similarity.sum(axis=1)  # 越大越不同

    # 选择差异最大的几张图
    selected_idx = np.argsort(diversity_score)[-NUM_SELECT:]
    for idx in selected_idx:
        src_path = features[idx][0]
        dst_path = os.path.join(OUTPUT_DIR, os.path.basename(src_path))
        shutil.copy(src_path, dst_path)



#pip install torch torchvision tqdm transformers

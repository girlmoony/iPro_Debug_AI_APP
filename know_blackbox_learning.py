前提：EfficientNet-B0 モデル定義（共通部分）
import torch
import torchvision.models as models
from torchvision import transforms
from PIL import Image

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# EfficientNet-B0 の読み込み（事前学習済み）
model = models.efficientnet_b0(pretrained=True)
model.eval().to(device)


① Grad-CAM：モデルが画像のどこに注目したか
from torchcam.methods import GradCAM
import matplotlib.pyplot as plt
import numpy as np

# Grad-CAM 設定（EfficientNet の最終畳み込み層名）
cam_extractor = GradCAM(model, target_layer="features.7.2")

# 入力画像を読み込み・前処理
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor()
])
image = transform(Image.open("example.jpg")).unsqueeze(0).to(device)

# 順伝播して予測
output = model(image)
pred_class = output.argmax().item()

# CAM 抽出
activation_map = cam_extractor(pred_class, output)[0].cpu().numpy()

# 可視化
plt.imshow(activation_map, cmap='jet', alpha=0.5)
plt.title(f"Grad-CAM: predicted class {pred_class}")
plt.axis("off")
plt.show()


② 勾配の監視：どの層が学習されているかを確認
# loss.backward() の直後に挿入
for name, param in model.named_parameters():
    if param.grad is not None:
        print(f"{name:50s} | grad norm: {param.grad.norm():.6f}")
    else:
        print(f"{name:50s} | grad: None (可能性: 凍結中)")

loss.backward()
# 🔽 ここに挿入
[このコード]
optimizer.step()

from sklearn.manifold import TSNE
import matplotlib.pyplot as plt

features = []
labels_all = []

# 中間特徴を抽出するためのフック付きモデル定義
class FeatureExtractor(torch.nn.Module):
    def __init__(self, base_model):
        super().__init__()
        self.features = base_model.features
        self.avgpool = base_model.avgpool

    def forward(self, x):
        x = self.features(x)
        x = self.avgpool(x)
        x = torch.flatten(x, 1)  # Flatten before classifier
        return x

feature_model = FeatureExtractor(model).to(device)
feature_model.eval()

# データローダー例（仮）
from torchvision.datasets import FakeData
from torch.utils.data import DataLoader

dataset = FakeData(size=200, image_size=(3, 224, 224), num_classes=5, transform=transform)
loader = DataLoader(dataset, batch_size=32, shuffle=False)

# 特徴抽出
with torch.no_grad():
    for images, labels in loader:
        images = images.to(device)
        feats = feature_model(images).cpu()
        features.append(feats)
        labels_all.extend(labels)

features = torch.cat(features).numpy()

# TSNE
tsne = TSNE(n_components=2, random_state=42)
features_2d = tsne.fit_transform(features)

# 可視化
plt.figure(figsize=(10, 8))
plt.scatter(features_2d[:, 0], features_2d[:, 1], c=labels_all, cmap='tab10', s=10)
plt.title("EfficientNet Features (TSNE)")
plt.colorbar()
plt.show()




for epoch in range(num_epochs):
    model.train()
    for inputs, labels in train_loader:
        ...
        loss.backward()

        # ✅ 勾配監視はここ
        for name, param in model.named_parameters():
            if param.grad is not None:
                print(f"{name}: grad norm = {param.grad.norm():.4f}")

        optimizer.step()

# === 学習後 or 検証中 ===
model.eval()
for inputs, labels in test_loader:
    outputs = model(inputs)
    preds = outputs.argmax(dim=1)

    # ✅ Grad-CAM / Saliency Map ここで実施
    # ✅ TSNE用の中間特徴もここで抽出

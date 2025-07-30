import torch
import torch.nn as nn
from torchvision import models, transforms, datasets
from torch.utils.data import DataLoader
from torch.quantization import get_default_qat_qconfig, prepare_qat, convert

# === 0. 環境・パラメータ設定 ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
num_classes = 288
batch_size = 32
epochs_stage1 = 5
epochs_stage2 = 10

# === 1. データローダー（必要に応じてパス変更） ===
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])
train_dataset = datasets.ImageFolder(root='train_data_path', transform=transform)
train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True)

# === 2. モデルロード（284クラス事前学習済み）===
model = models.efficientnet_b0(pretrained=False)

# 旧分類層（284クラス）を仮定して読み込み
in_features = model.classifier[1].in_features
model.classifier[1] = nn.Linear(in_features, 284)
model.load_state_dict(torch.load("efficientnet_b0_pretrained_284.pth"))

# === 3. 分類層を288クラスに置換 ===
model.classifier[1] = nn.Linear(in_features, num_classes)

# === 4. ステージ1：分類層のみ学習 ===
# → バックボーンを凍結
for param in model.parameters():
    param.requires_grad = False
for param in model.classifier.parameters():
    param.requires_grad = True

# QAT準備（この段階でやってOK）
model.qconfig = get_default_qat_qconfig('fbgemm')
model = prepare_qat(model)
model.to(device)

# 最適化対象は分類層のみ
optimizer = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()), lr=1e-4)
criterion = nn.CrossEntropyLoss()

# ステージ1訓練
for epoch in range(epochs_stage1):
    model.train()
    running_loss = 0.0
    for inputs, labels in train_loader:
        inputs, labels = inputs.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        running_loss += loss.item()
    print(f"[Stage 1] Epoch {epoch+1}/{epochs_stage1} - Loss: {running_loss:.4f}")

# === 5. ステージ2：全層をアンフリーズして微調整（QAT付き） ===
for param in model.parameters():
    param.requires_grad = True

optimizer = torch.optim.Adam(model.parameters(), lr=1e-5)
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)

# ステージ2訓練
for epoch in range(epochs_stage2):
    model.train()
    running_loss = 0.0
    for inputs, labels in train_loader:
        inputs, labels = inputs.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        running_loss += loss.item()
    scheduler.step()
    print(f"[Stage 2] Epoch {epoch+1}/{epochs_stage2} - Loss: {running_loss:.4f}")

# === 6. モデルを量子化（int8）して保存 ===
model.cpu()
model.eval()
model_int8 = convert(model)
torch.save(model_int8.state_dict(), "efficientnet_b0_qat_2stage_288.pth")

import torch
import torch.nn as nn
from torchvision.models import efficientnet_b0
from torch.quantization import get_default_qat_qconfig, prepare_qat
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

# === 1. 環境とモデル設定 ===
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
num_classes = 288  # 例：284 + 4クラス

# ImageNetベースのモデル読み込み
model = efficientnet_b0(pretrained=True)
model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)

# 全層学習可能にする
for param in model.parameters():
    param.requires_grad = True

# === 2. QATの準備 ===
model.train()
model.qconfig = get_default_qat_qconfig('fbgemm')
model_prepared = prepare_qat(model)  # fake-quantとobserverを挿入
model_prepared.to(device)

# === 3. データセット読み込み ===
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])
train_dataset = datasets.ImageFolder("train_path", transform=transform)
val_dataset = datasets.ImageFolder("val_path", transform=transform)
train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)

# === 4. キャリブレーション（数バッチ通して安定化） ===
model_prepared.eval()
with torch.no_grad():
    for i, (inputs, _) in enumerate(train_loader):
        model_prepared(inputs.to(device))
        if i >= 10:  # 数バッチでOK
            break

# === 5. QATトレーニング ===
model_prepared.train()
optimizer = torch.optim.Adam(model_prepared.parameters(), lr=1e-5)
scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.5)
criterion = nn.CrossEntropyLoss()

best_acc = 0.0
for epoch in range(1, 21):
    # --- Train ---
    model_prepared.train()
    total_loss, total_correct, total_samples = 0, 0, 0
    for inputs, labels in train_loader:
        inputs, labels = inputs.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model_prepared(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += loss.item() * inputs.size(0)
        total_correct += (outputs.argmax(1) == labels).sum().item()
        total_samples += labels.size(0)

    train_loss = total_loss / total_samples
    train_acc = total_correct / total_samples

    # --- Validation ---
    model_prepared.eval()
    val_loss, val_correct, val_total = 0, 0, 0
    with torch.no_grad():
        for inputs, labels in val_loader:
            inputs, labels = inputs.to(device), labels.to(device)
            outputs = model_prepared(inputs)
            loss = criterion(outputs, labels)
            val_loss += loss.item() * inputs.size(0)
            val_correct += (outputs.argmax(1) == labels).sum().item()
            val_total += labels.size(0)

    val_loss /= val_total
    val_acc = val_correct / val_total

    print(f"Epoch {epoch} | Train Loss: {train_loss:.4f} | Train Acc: {train_acc:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.4f}")

    # --- Save best model ---
    if val_acc > best_acc:
        best_acc = val_acc
        torch.save(model_prepared.state_dict(), "best_model_qat.pth")

    scheduler.step()

# === 6. 学習完了後に保存用にCPUに移動 ===
model_prepared.eval()
model_prepared.cpu()
torch.save(model_prepared.state_dict(), "qat_model_final.pth")
print("✅ モデルをCPUに移して保存しました。")

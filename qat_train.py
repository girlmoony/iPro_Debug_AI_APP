import torch
import torch.nn as nn
from torchvision.models import efficientnet_b0
from torch.quantization import get_default_qat_qconfig, prepare_qat
from torchvision import datasets, transforms
from torch.utils.data import DataLoader

# --- 1. モデルの読み込みと全層Unfreeze ---
model = efficientnet_b0(pretrained=True)
model.classifier[1] = nn.Linear(model.classifier[1].in_features, num_classes)  # 例: num_classes=288

for param in model.parameters():
    param.requires_grad = True  # 全層Unfreeze

# --- 2. QAT準備（fuse_modelはEfficientNetでは省略） ---
model.train()
model.qconfig = get_default_qat_qconfig('fbgemm')
model_prepared = prepare_qat(model)

# --- 3. データローダー ---
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
])
train_dataset = datasets.ImageFolder(root='train_data_path', transform=transform)
train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True)

# --- 4. Optimizer & Scheduler ---
optimizer = torch.optim.Adam(model_prepared.parameters(), lr=1e-5)
scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=20)

# --- 5. QATトレーニング ---
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model_prepared.to(device)
criterion = nn.CrossEntropyLoss()

for epoch in range(20):  # 適宜調整
    model_prepared.train()
    total_loss = 0.0
    for inputs, labels in train_loader:
        inputs, labels = inputs.to(device), labels.to(device)
        optimizer.zero_grad()
        outputs = model_prepared(inputs)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    scheduler.step()
    print(f"Epoch {epoch+1} - Loss: {total_loss:.4f}")

# --- 6. モデル保存（ONNX出力はしない） ---
model_prepared.cpu()
model_prepared.eval()
torch.save(model_prepared.state_dict(), "qat_model_final.pth")

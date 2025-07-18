import torch
import torch.nn as nn
from torch.optim import AdamW
from torch.utils.data import DataLoader
from torchvision.models import efficientnet_b0
from early_stopping import EarlyStopping  # 自定义早停类
from qat_utils import prepare_qat  # 可选：量子化准备
import time

def freeze_layers(model, freeze_until='blocks.6'):
    """冻结模型参数直到指定层"""
    for name, param in model.named_parameters():
        if freeze_until in name or 'classifier' in name:
            param.requires_grad = True
        else:
            param.requires_grad = False

def train_one_phase(model, train_loader, val_loader, phase_name, num_epochs, criterion, optimizer, early_stopping):
    print(f"\n🟡 Start Phase: {phase_name} for {num_epochs} epochs")
    for epoch in range(num_epochs):
        model.train()
        for data, target in train_loader:
            data, target = data.to(device), target.to(device)
            optimizer.zero_grad()
            output = model(data)
            loss = criterion(output, target)
            loss.backward()
            optimizer.step()

        # Validation
        model.eval()
        val_loss, correct, total = 0, 0, 0
        with torch.no_grad():
            for data, target in val_loader:
                data, target = data.to(device), target.to(device)
                output = model(data)
                val_loss += criterion(output, target).item()
                pred = output.argmax(1)
                correct += (pred == target).sum().item()
                total += target.size(0)

        val_acc = correct / total
        print(f"[{phase_name}] Epoch {epoch+1}: Val Loss={val_loss:.4f}, Val Acc={val_acc:.4f}")
        
        early_stopping(val_acc, model)
        if early_stopping.early_stop:
            print("✅ Early stopping triggered.")
            break

# ==== MAIN TRAINING SCRIPT ====

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = efficientnet_b0(pretrained=True)
model.classifier[1] = nn.Linear(model.classifier[1].in_features, 288)  # 修改为284+4类
model = model.to(device)

train_loader = DataLoader(...)  # 自定义加载
val_loader = DataLoader(...)

criterion = nn.CrossEntropyLoss()
optimizer = AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=3e-4)

# ---- Phase 1: Classifier Only ----
freeze_layers(model, freeze_until='classifier')
early_stopping = EarlyStopping(patience=3, mode='max', monitor='acc', save_path='best_phase1.pth')
train_one_phase(model, train_loader, val_loader, "Phase 1 - Classifier Only", num_epochs=6, criterion=criterion, optimizer=optimizer, early_stopping=early_stopping)

# ---- Phase 2: Block6 + Block7 + FC ----
freeze_layers(model, freeze_until='blocks.6')  # 解冻 block6 以后
optimizer = AdamW(filter(lambda p: p.requires_grad, model.parameters()), lr=1e-4)
early_stopping = EarlyStopping(patience=3, mode='max', monitor='acc', save_path='best_phase2.pth')
train_one_phase(model, train_loader, val_loader, "Phase 2 - Block6+", num_epochs=10, criterion=criterion, optimizer=optimizer, early_stopping=early_stopping)

# ---- Phase 3: All layers fine-tune ----
for param in model.parameters():
    param.requires_grad = True
optimizer = AdamW(model.parameters(), lr=5e-5)
early_stopping = EarlyStopping(patience=3, mode='max', monitor='acc', save_path='best_phase3.pth')
train_one_phase(model, train_loader, val_loader, "Phase 3 - Full FineTune", num_epochs=12, criterion=criterion, optimizer=optimizer, early_stopping=early_stopping)

# ---- Phase 4: QAT (optional) ----
# 准备量子化模型（可选）
from torch.quantization import get_default_qat_qconfig
model.qconfig = get_default_qat_qconfig('fbgemm')
model.train()
model = torch.quantization.prepare_qat(model)

optimizer = AdamW(model.parameters(), lr=1e-5)
early_stopping = EarlyStopping(patience=2, mode='max', monitor='acc', save_path='best_qat.pth')
train_one_phase(model, train_loader, val_loader, "Phase 4 - QAT", num_epochs=6, criterion=criterion, optimizer=optimizer, early_stopping=early_stopping)

# 最终保存
torch.save(model.state_dict(), "final_model.pth")
print("✅ 完成全部训练阶段。")


import torch
from torch import nn, optim
from torch.optim.lr_scheduler import StepLR

# モデルとデバイス
device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
model = YourEfficientNetModel()  # 例: timm.create_model('efficientnet_b4', pretrained=True)
model.classifier = nn.Linear(in_features=model.classifier.in_features, out_features=288)
model = model.to(device)

# =============================
# Layer解凍関数
# =============================
def unfreeze_layers(model, epoch):
    # 全て一度凍結
    for param in model.parameters():
        param.requires_grad = False

    # classifier は常に解凍
    for param in model.classifier.parameters():
        param.requires_grad = True

    if epoch >= 20:
        for name, param in model.named_parameters():
            if any(b in name for b in ['blocks.7', 'blocks.8']):
                param.requires_grad = True

    if epoch >= 40:
        for name, param in model.named_parameters():
            if 'blocks.6' in name:
                param.requires_grad = True

    if epoch >= 60:
        for param in model.parameters():
            param.requires_grad = True

# =============================
# Optimizer + Scheduler
# =============================
def setup_optimizer_and_scheduler(model, epoch):
    if epoch < 20:
        lr = 1e-3
    elif epoch < 40:
        lr = 1e-4
    elif epoch < 60:
        lr = 1e-5
    else:
        lr = 5e-6

    params_to_update = [p for p in model.parameters() if p.requires_grad]
    optimizer = optim.Adam(params_to_update, lr=lr)
    scheduler = StepLR(optimizer, step_size=10, gamma=0.9)  # 10epochごとにLRを減衰
    return optimizer, scheduler

# =============================
# 学習ループ
# =============================
num_epochs = 100
best_acc = 0.0

for epoch in range(num_epochs):
    print(f"\nEpoch {epoch+1}/{num_epochs}")

    # 段階的に解凍
    unfreeze_layers(model, epoch)

    # optimizerとscheduler再設定
    optimizer, scheduler = setup_optimizer_and_scheduler(model, epoch)

    # ========== Training ==========
    model.train()
    running_loss = 0.0
    correct = 0

    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)

        optimizer.zero_grad()
        outputs = model(images)
        loss = nn.CrossEntropyLoss()(outputs, labels)
        loss.backward()
        optimizer.step()

        running_loss += loss.item() * images.size(0)
        correct += (outputs.argmax(1) == labels).sum().item()

    epoch_loss = running_loss / len(train_dataset)
    epoch_acc = correct / len(train_dataset)
    print(f"Train Loss: {epoch_loss:.4f}, Acc: {epoch_acc:.4f}")

    # ========== Validation ==========
    model.eval()
    val_correct = 0

    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            val_correct += (outputs.argmax(1) == labels).sum().item()

    val_acc = val_correct / len(val_dataset)
    print(f"Validation Acc: {val_acc:.4f}")

    # モデル保存
    if val_acc > best_acc:
        best_acc = val_acc
        torch.save(model.state_dict(), 'best_model.pt')
        print(f"✅ Best model updated: {best_acc:.4f}")

    # scheduler step
    scheduler.step()



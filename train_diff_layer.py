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

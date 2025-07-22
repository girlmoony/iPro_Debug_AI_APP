import torch
import torch.nn as nn
import torch.optim as optim
from torchvision.models import efficientnet_b0
from torch.optim.lr_scheduler import CosineAnnealingLR, ReduceLROnPlateau
from tqdm import tqdm

# =============================
# Layer 段階解凍
# =============================
def unfreeze_layers(model, epoch):
    for param in model.parameters():
        param.requires_grad = False

    for param in model.classifier.parameters():
        param.requires_grad = True

    if epoch >= 10:
        for name, param in model.named_parameters():
            if any(f'features.{i}' in name for i in [7, 8]):
                param.requires_grad = True

    if epoch >= 20:
        for name, param in model.named_parameters():
            if any(f'features.{i}' in name for i in [5, 6]):
                param.requires_grad = True

    if epoch >= 40:
        for param in model.parameters():
            param.requires_grad = True

# =============================
# Optimizer 切替
# =============================
def setup_optimizer(model, epoch):
    params = [p for p in model.parameters() if p.requires_grad]

    if epoch < 30:
        optimizer = optim.Adam(params, lr=1e-3 if epoch < 10 else 1e-4)
    else:
        optimizer = optim.SGD(params, lr=1e-4, momentum=0.9)

    return optimizer

# =============================
# Optimizer + StepLR Scheduler
# =============================
def setup_optimizer_and_scheduler(model, epoch):
    params = [p for p in model.parameters() if p.requires_grad]

    if epoch < 30:
        optimizer = optim.Adam(params, lr=1e-3 if epoch < 10 else 1e-4)
    else:
        optimizer = optim.SGD(params, lr=1e-4, momentum=0.9)

    # StepLRを使う（15 epochごとに lr を半分に）
    scheduler = torch.optim.lr_scheduler.StepLR(optimizer, step_size=15, gamma=0.5)

    return optimizer, scheduler

# =============================
# Main トレーニングループ
# =============================
def main(train_loader, val_loader, train_dataset, val_dataset, num_epochs=60):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # 学習済みモデルを読み込み（出力層は後で置換）
    model = efficientnet_b0(pretrained=False)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, 288)
    model.load_state_dict(torch.load('efficientnet284_pretrained.pt'))  # ← あなたの284クラスモデル
    model = model.to(device)

    best_acc = 0.0
    cosine_scheduler = None
    plateau_scheduler = None

    for epoch in range(num_epochs):
        print(f"\nEpoch {epoch + 1}/{num_epochs}")

        # 解凍設定
        unfreeze_layers(model, epoch)

        # optimizer 再構築
        optimizer = setup_optimizer(model, epoch)
        

        # scheduler 準備
        if epoch < 30:
            cosine_scheduler = CosineAnnealingLR(optimizer, T_max=30, eta_min=5e-6)
        else:
            if plateau_scheduler is None:  # 最初の一度だけ作成
                plateau_scheduler = ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=5, min_lr=1e-6, verbose=True)

        # ========= Training =========
        model.train()
        running_loss = 0.0
        correct = 0

        for images, labels in tqdm(train_loader, desc="Training"):
            images, labels = images.to(device), labels.to(device)

            optimizer.zero_grad()
            outputs = model(images)
            loss = nn.CrossEntropyLoss()(outputs, labels)
            loss.backward()
            optimizer.step()

            running_loss += loss.item() * images.size(0)
            correct += (outputs.argmax(1) == labels).sum().item()

        train_acc = correct / len(train_dataset)
        print(f"Train Acc: {train_acc:.4f}")

        # ========= Validation =========
        model.eval()
        val_correct = 0

        with torch.no_grad():
            for images, labels in tqdm(val_loader, desc="Validation"):
                images, labels = images.to(device), labels.to(device)
                outputs = model(images)
                val_correct += (outputs.argmax(1) == labels).sum().item()

        val_acc = val_correct / len(val_dataset)
        print(f"Validation Acc: {val_acc:.4f}")

        # 最良モデル保存
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), 'best_model_288.pt')
            print(f"✅ Best model saved: {best_acc:.4f}")

        # scheduler step
        if epoch < 30:
            cosine_scheduler.step()
        else:
            plateau_scheduler.step(val_acc)

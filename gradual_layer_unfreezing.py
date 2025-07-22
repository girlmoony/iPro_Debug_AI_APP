torchvision EfficientNet 構造（features[0]～[8], classifier）に対応した、段階的に layer を解凍しながら、前半は CosineAnnealingLR、後半は ReduceLROnPlateau を使った training loop

import torch
import torch.nn as nn
import torch.optim as optim
from torchvision.models import efficientnet_b0
from torch.optim.lr_scheduler import CosineAnnealingLR, ReduceLROnPlateau
from tqdm import tqdm

# =============================
# Layer 解凍関数
# =============================
def unfreeze_layers(model, epoch):
    # 一度全部freeze
    for param in model.parameters():
        param.requires_grad = False

    # classifier は常に解凍
    for param in model.classifier.parameters():
        param.requires_grad = True

    # epoch >= 20: features[7], [8] を解凍
    if epoch >= 20:
        for name, param in model.named_parameters():
            if any(f"features.{i}" in name for i in [7, 8]):
                param.requires_grad = True

    # epoch >= 40: features[5], [6] を追加で解凍
    if epoch >= 40:
        for name, param in model.named_parameters():
            if any(f"features.{i}" in name for i in [5, 6]):
                param.requires_grad = True

    # epoch >= 60: 全層解凍
    if epoch >= 60:
        for param in model.parameters():
            param.requires_grad = True

# =============================
# optimizer は epoch ごとに再構築
# =============================
def setup_optimizer(model, epoch):
    if epoch < 20:
        lr = 1e-3
    elif epoch < 40:
        lr = 1e-4
    elif epoch < 60:
        lr = 1e-5
    else:
        lr = 5e-6

    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = optim.Adam(params, lr=lr)
    return optimizer

# =============================
# メイン関数
# =============================
def main(train_loader, val_loader, train_dataset, val_dataset, num_epochs=100):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    # モデル作成（288クラス用にclassifier置換）
    model = efficientnet_b0(pretrained=True)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, 288)
    model = model.to(device)

    best_acc = 0.0

    # 最初のoptimizerとschedulersの準備
    optimizer = setup_optimizer(model, epoch=0)
    cosine_scheduler = CosineAnnealingLR(optimizer, T_max=70, eta_min=5e-6)
    plateau_scheduler = ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=5, min_lr=1e-6, verbose=True)

    for epoch in range(num_epochs):
        print(f"\nEpoch {epoch + 1}/{num_epochs}")

        # Layerの段階解凍
        unfreeze_layers(model, epoch)

        # optimizerは学習率が変わる可能性があるので再構築
        optimizer = setup_optimizer(model, epoch)

        # scheduler更新（再利用）
        if epoch < 70:
            scheduler = cosine_scheduler
        else:
            scheduler = plateau_scheduler

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

        epoch_loss = running_loss / len(train_dataset)
        epoch_acc = correct / len(train_dataset)
        print(f"Train Loss: {epoch_loss:.4f}, Acc: {epoch_acc:.4f}")

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

        # ベストモデル保存
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), 'best_model.pt')
            print(f"✅ Best model updated: {best_acc:.4f}")

        # scheduler step
        if epoch < 70:
            cosine_scheduler.step()
        else:
            plateau_scheduler.step(val_acc)

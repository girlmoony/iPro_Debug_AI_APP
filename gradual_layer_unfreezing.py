import torch
import torch.nn as nn
import torch.optim as optim
from torchvision.models import efficientnet_b0
from torch.optim.lr_scheduler import CosineAnnealingLR, ReduceLROnPlateau
from tqdm import tqdm

def unfreeze_layers(model, epoch, mode='partial'):
    """
    mode='partial': 段階的にfeatures.7→5→3→0を解凍（推奨）
    mode='full': 80epoch以降で全層解凍
    mode='freeze_low': features.0〜2は常に凍結
    """
    for param in model.parameters():
        param.requires_grad = False

    for param in model.classifier.parameters():
        param.requires_grad = True

    if epoch >= 20:
        for name, param in model.named_parameters():
            if "features.7" in name or "features.8" in name:
                param.requires_grad = True

    if epoch >= 40:
        for name, param in model.named_parameters():
            if "features.5" in name or "features.6" in name:
                param.requires_grad = True

    if epoch >= 60:
        for name, param in model.named_parameters():
            if "features.3" in name or "features.4" in name:
                param.requires_grad = True

    if mode == 'partial' and epoch >= 80:
        for name, param in model.named_parameters():
            if "features.0" in name or "features.1" in name or "features.2" in name:
                param.requires_grad = True

    if mode == 'full' and epoch >= 80:
        for param in model.parameters():
            param.requires_grad = True

    if mode == 'freeze_low' and epoch >= 80:
        # 全部解凍したいが浅層（features.0〜2）は除く
        for name, param in model.named_parameters():
            if "features.0" not in name and "features.1" not in name and "features.2" not in name:
                param.requires_grad = True

# ========== 段階的にLayerを解凍 ==========
def unfreeze_layers(model, epoch):
    for param in model.parameters():
        param.requires_grad = False  # 一旦全てfreeze

    # classifierは常に解凍
    for param in model.classifier.parameters():
        param.requires_grad = True

    if epoch >= 20:
        for name, param in model.named_parameters():
            if any(f"features.{i}" in name for i in [7, 8]):
                param.requires_grad = True
    if epoch >= 40:
        for name, param in model.named_parameters():
            if any(f"features.{i}" in name for i in [5, 6]):
                param.requires_grad = True
    if epoch >= 60:
        for param in model.parameters():
            param.requires_grad = True

# ========== Optimizerのセットアップ ==========
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
    return optim.Adam(params, lr=lr)

# ========== メイン関数 ==========
def main(train_loader, val_loader, train_dataset, val_dataset, num_epochs=100):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    model = efficientnet_b0(pretrained=True)
    model.classifier[1] = nn.Linear(model.classifier[1].in_features, 288)
    model = model.to(device)

    best_acc = 0.0

    for epoch in range(num_epochs):
        print(f"\nEpoch {epoch+1}/{num_epochs}")

        # 段階的にLayerを解凍
        unfreeze_layers(model, epoch)

        # optimizer 再構築
        optimizer = setup_optimizer(model, epoch)

        # scheduler 再構築（毎回）
        cosine_scheduler = CosineAnnealingLR(optimizer, T_max=70, eta_min=5e-6)
        plateau_scheduler = ReduceLROnPlateau(optimizer, mode='max', factor=0.5, patience=5, verbose=True)

        scheduler = cosine_scheduler if epoch < 70 else plateau_scheduler

        # ========= トレーニング =========
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

        # ========= 検証 =========
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
            torch.save(model.state_dict(), "best_model.pt")
            print(f"✅ Best model updated: {best_acc:.4f}")

        # scheduler更新
        if isinstance(scheduler, ReduceLROnPlateau):
            scheduler.step(val_acc)
        else:
            scheduler.step()

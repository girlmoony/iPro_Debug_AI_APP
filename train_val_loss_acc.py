from torch.utils.tensorboard import SummaryWriter

# TensorBoard用のログ出力先を定義（runs/experiment1 など）
writer = SummaryWriter(log_dir='runs/exp1')  # 任意の名前でOK

for epoch in range(num_epochs):
    # === Trainフェーズ ===
    model.train()
    train_loss = 0.0
    correct_train = 0
    total_train = 0

    for images, labels in train_loader:
        images, labels = images.to(device), labels.to(device)
        optimizer.zero_grad()

        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        train_loss += loss.item() * images.size(0)
        _, predicted = outputs.max(1)
        correct_train += (predicted == labels).sum().item()
        total_train += labels.size(0)

    avg_train_loss = train_loss / total_train
    train_accuracy = correct_train / total_train

    # === Validationフェーズ ===
    model.eval()
    val_loss = 0.0
    correct_val = 0
    total_val = 0

    with torch.no_grad():
        for images, labels in val_loader:
            images, labels = images.to(device), labels.to(device)
            outputs = model(images)
            loss = criterion(outputs, labels)

            val_loss += loss.item() * images.size(0)
            _, predicted = outputs.max(1)
            correct_val += (predicted == labels).sum().item()
            total_val += labels.size(0)

    avg_val_loss = val_loss / total_val
    val_accuracy = correct_val / total_val

    # === TensorBoardに出力 ===
    writer.add_scalar('Loss/train', avg_train_loss, epoch)
    writer.add_scalar('Loss/val', avg_val_loss, epoch)
    writer.add_scalar('Accuracy/train', train_accuracy, epoch)
    writer.add_scalar('Accuracy/val', val_accuracy, epoch)

    # ログファイルにも出力（任意）
    logging.info(f"Epoch {epoch+1}, Train Loss: {avg_train_loss:.4f}, Train Acc: {train_accuracy:.2%}, Val Loss: {avg_val_loss:.4f}, Val Acc: {val_accuracy:.2%}")

# 最後に明示的にclose
writer.close()

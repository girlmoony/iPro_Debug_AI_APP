import time

# トレーニングデータ読み込み時間を計測
train_total_time = 0
for epoch in range(10):
    start = time.time()
    for batch in train_loader:
        pass  # データを読み込むだけ、何もしない
    end = time.time()
    epoch_time = end - start
    train_total_time += epoch_time
    print(f"[Train] Epoch {epoch+1}: {epoch_time:.2f} sec")

# 検証データ読み込み時間を計測
val_total_time = 0
for epoch in range(10):
    start = time.time()
    for batch in val_loader:
        pass
    end = time.time()
    epoch_time = end - start
    val_total_time += epoch_time
    print(f"[Val] Epoch {epoch+1}: {epoch_time:.2f} sec")

print(f"\n[Summary] Avg train load time per epoch: {train_total_time / 10:.2f} sec")
print(f"[Summary] Avg val load time per epoch:   {val_total_time / 10:.2f} sec")

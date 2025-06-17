import os
import shutil
import pandas as pd
from pathlib import Path

# 設定
base_dir = Path("datasets")
excel_path = Path("folder_mapping.xlsx")

# Excel読み込み
df = pd.read_excel(excel_path, usecols=[0, 1])
df.columns = ['old_name', 'new_name']

rename_count = 0
rename_log = []  # 衝突時のファイル名ログ

for old_name, new_name in df.itertuples(index=False):
    old_path = base_dir / old_name
    new_path = base_dir / new_name

    if not old_path.exists() or not old_path.is_dir():
        print(f"スキップ（存在しないフォルダ）: {old_name}")
        continue

    if new_path.exists():
        print(f"フォルダ {new_name} は既に存在 → PNGを移動")
        for file in old_path.glob("*.png"):
            dest = new_path / file.name
            if dest.exists():
                base, ext = os.path.splitext(file.name)
                count = 1
                while (new_path / f"{base}_{count}{ext}").exists():
                    count += 1
                new_filename = f"{base}_{count}{ext}"
                dest = new_path / new_filename
                rename_log.append((file.name, new_filename))  # ログ追加
                rename_count += 1
            shutil.move(str(file), str(dest))
        try:
            old_path.rmdir()
        except OSError:
            pass
    else:
        old_path.rename(new_path)
        print(f"フォルダ名を変更: {old_name} → {new_name}")

# 結果出力
print(f"\n🔁 リネームされたファイル数: {rename_count}")
if rename_log:
    print("\n📝 リネームログ（元名 → 新名）:")
    for old, new in rename_log:
        print(f" - {old} → {new}")

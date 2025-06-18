import os
import shutil
import pandas as pd
from pathlib import Path
import re

# 設定
base_dir = Path("datasets")
excel_path = Path("folder_mapping.xlsx")

# Excel読み込み
df = pd.read_excel(excel_path, dtype=str).astype(str)

rename_count = 0
rename_log = []

for folder in base_dir.iterdir():
    if not folder.is_dir():
        continue

    # フォルダ名から commodity_id を抽出（例: '99_あまえび' → '99'）
    match = re.match(r'^(\d+)', folder.name)
    if not match:
        print(f"スキップ（数字が見つからない）: {folder.name}")
        continue

    commodity_id = match.group(1)

    # commodity_id から 学習class_id を取得
    row_commodity = df[df['commodity_id'] == commodity_id]
    if row_commodity.empty:
        print(f"commodity_idが見つからない: {commodity_id}")
        continue

    class_id = row_commodity['学習class_id'].values[0]

    # classid_classname列から class_id に一致するもの（アンダースコア前）を探す
    matched_row = df[df['classid_classname'].str.match(f'^{class_id}_')]
    if matched_row.empty:
        print(f"学習class_id={class_id} に一致する classid_classname が見つからない")
        continue

    new_folder_name = matched_row['classid_classname'].values[0]
    new_folder_path = base_dir / new_folder_name

    if new_folder_path.exists():
        print(f"フォルダ {new_folder_name} は既に存在 → PNGを移動")
        for file in folder.glob("*.png"):
            dest = new_folder_path / file.name
            if dest.exists():
                base, ext = os.path.splitext(file.name)
                count = 1
                while (new_folder_path / f"{base}_{count}{ext}").exists():
                    count += 1
                new_filename = f"{base}_{count}{ext}"
                dest = new_folder_path / new_filename
                rename_log.append((file.name, new_filename))
                rename_count += 1
            shutil.move(str(file), str(dest))
        try:
            folder.rmdir()
        except OSError:
            pass
    else:
        folder.rename(new_folder_path)
        print(f"フォルダ名を変更: {folder.name} → {new_folder_name}")

# 結果出力
print(f"\n🔁 リネームされたファイル数: {rename_count}")
if rename_log:
    print("\n📝 リネームログ（元名 → 新名）:")
    for old, new in rename_log:
        print(f" - {old} → {new}")



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

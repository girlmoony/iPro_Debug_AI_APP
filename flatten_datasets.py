import os
import shutil

def flatten_dataset_structure(src_root, dst_root):
    if not os.path.exists(dst_root):
        os.makedirs(dst_root)

    for class_name in os.listdir(src_root):
        class_path = os.path.join(src_root, class_name)
        if not os.path.isdir(class_path):
            continue

        dst_class_path = os.path.join(dst_root, class_name)
        os.makedirs(dst_class_path, exist_ok=True)

        for item in os.listdir(class_path):
            item_path = os.path.join(class_path, item)

            if os.path.isdir(item_path):  # 日付フォルダ
                for file in os.listdir(item_path):
                    if file.endswith(".png"):
                        src_file = os.path.join(item_path, file)
                        dst_file = os.path.join(dst_class_path, file)
                        # ファイル名衝突対策
                        if os.path.exists(dst_file):
                            base, ext = os.path.splitext(file)
                            count = 1
                            while True:
                                new_name = f"{base}_{count}{ext}"
                                dst_file = os.path.join(dst_class_path, new_name)
                                if not os.path.exists(dst_file):
                                    break
                                count += 1
                        shutil.move(src_file, dst_file)

                # 空のフォルダは削除（任意）
                if not os.listdir(item_path):
                    os.rmdir(item_path)

            elif item.endswith(".png"):  # 既にクラス直下の画像
                shutil.move(item_path, os.path.join(dst_class_path, item))

# 使用例
flatten_dataset_structure("datasets_XX", "datasets")

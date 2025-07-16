#!/bin/bash

# === 結果保存先ディレクトリ ===
RESULT_DIR="results"
mkdir -p "$RESULT_DIR"
mkdir -p "models"

# === 学習パラメータの組み合わせ ===
declare -a learning_rates=("0.001" "0.0005" "0.0001")
declare -a batch_sizes=("64" "32" "128")

# === 実験開始 ===
for i in ${!learning_rates[@]}; do
    lr=${learning_rates[$i]}
    bs=${batch_sizes[$i]}
    tag="lr${lr}_bs${bs}"
    model_name="model_${tag}.pth"
    model_path="models/${model_name}"

    echo "==============================="
    echo "▶ 実行中: $tag"
    echo "==============================="

    # --- 学習 ---
    python train.py --lr "$lr" --batch_size "$bs" --save_name "$model_name"
    if [ $? -ne 0 ]; then
        echo "❌ train.py 失敗: $tag"
        continue
    fi

    # --- テスト ---
    python test_model.py --model_path "$model_path"
    if [ $? -ne 0 ]; then
        echo "❌ test_model.py 失敗: $tag"
        continue
    fi

    # --- 結果ファイルのコピー・リネーム ---
    cp classification_report.txt "${RESULT_DIR}/classification_report_${tag}.txt"
    cp wrong_image_list.csv     "${RESULT_DIR}/wrong_image_list_${tag}.csv"
    cp confusion_matrix.png     "${RESULT_DIR}/confusion_matrix_${tag}.png"

    echo "✅ 完了: $tag"
done

echo "✅ すべての実験が完了しました。"

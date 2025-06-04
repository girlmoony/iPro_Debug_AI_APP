#include <vector>
#include <iostream>
#include <fstream>
#include <algorithm>

const int NUM_CLASSES = 288;

// 間違いやすいクラスのペアを出力
void print_top_confused_pairs(const std::vector<int>& y_true, const std::vector<int>& y_pred) {
    std::vector<std::vector<int>> confusion(NUM_CLASSES, std::vector<int>(NUM_CLASSES, 0));

    for (size_t i = 0; i < y_true.size(); ++i) {
        confusion[y_true[i]][y_pred[i]]++;
    }

    std::vector<std::pair<std::pair<int, int>, int>> errors;
    for (int i = 0; i < NUM_CLASSES; ++i) {
        for (int j = 0; j < NUM_CLASSES; ++j) {
            if (i != j && confusion[i][j] > 0) {
                errors.push_back({{i, j}, confusion[i][j]});
            }
        }
    }

    std::sort(errors.begin(), errors.end(), [](const auto& a, const auto& b) {
        return a.second > b.second;
    });

    std::cout << "Top 10 Confused Class Pairs (True, Pred) and Count:\n";
    for (int i = 0; i < std::min(10, (int)errors.size()); ++i) {
        auto& pair = errors[i];
        std::cout << "(" << pair.first.first << ", " << pair.first.second << "): " << pair.second << "\n";
    }
}

// 混同行列を CSV に出力
void save_confusion_matrix_to_csv(const std::vector<int>& y_true, const std::vector<int>& y_pred, const std::string& filename) {
    std::vector<std::vector<int>> confusion(NUM_CLASSES, std::vector<int>(NUM_CLASSES, 0));

    for (size_t i = 0; i < y_true.size(); ++i) {
        confusion[y_true[i]][y_pred[i]]++;
    }

    std::ofstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Failed to open file: " << filename << std::endl;
        return;
    }

    // ヘッダー
    file << "true/pred";
    for (int j = 0; j < NUM_CLASSES; ++j) {
        file << "," << j;
    }
    file << "\n";

    // 各行（正解ラベル）
    for (int i = 0; i < NUM_CLASSES; ++i) {
        file << i;
        for (int j = 0; j < NUM_CLASSES; ++j) {
            file << "," << confusion[i][j];
        }
        file << "\n";
    }

    file.close();
    std::cout << "Confusion matrix saved to: " << filename << std::endl;
}


int main() {
    std::vector<int> y_true = { /* ラベルを入れてください */ };
    std::vector<int> y_pred = { /* ラベルを入れてください */ };

    print_top_confused_pairs(y_true, y_pred);
    save_confusion_matrix_to_csv(y_true, y_pred, "confusion_matrix.csv");

    return 0;
}
confusion_matrix.csv: 288x288 の行列。行が正解、列が予測

print_top_confused_pairs により、間違いやすいクラスペアのトップ10が標準出力に表示されます

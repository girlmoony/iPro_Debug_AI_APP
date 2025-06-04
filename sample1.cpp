#include <vector>
#include <string>
#include <unordered_map>
#include <map>
#include <set>
#include <iostream>
#include <algorithm>

#include <fstream>

void save_confusion_matrix_csv(
    const std::vector<std::vector<int>>& confusion,
    const std::vector<std::string>& id_to_label,
    const std::string& filename
) {
    std::ofstream file(filename);
    if (!file.is_open()) {
        std::cerr << "Could not open file for writing: " << filename << std::endl;
        return;
    }

    // ヘッダー行
    file << "true/pred";
    for (const auto& label : id_to_label) {
        file << "," << label;
    }
    file << "\n";

    // 行：正解ラベル
    for (size_t i = 0; i < id_to_label.size(); ++i) {
        file << id_to_label[i];  // ラベル名（例："100_えび"）
        for (size_t j = 0; j < id_to_label.size(); ++j) {
            file << "," << confusion[i][j];
        }
        file << "\n";
    }

    file.close();
    std::cout << "Confusion matrix saved to CSV: " << filename << std::endl;
}

void print_top_confused_pairs(const std::vector<std::string>& y_true, const std::vector<std::string>& y_pred) {
    // 1. クラス名を整数にマッピング
    std::set<std::string> class_names(y_true.begin(), y_true.end());
    class_names.insert(y_pred.begin(), y_pred.end());

    std::map<std::string, int> label_to_id;
    std::vector<std::string> id_to_label;

    int idx = 0;
    for (const auto& label : class_names) {
        label_to_id[label] = idx++;
        id_to_label.push_back(label);
    }

    int num_classes = id_to_label.size();
    std::vector<std::vector<int>> confusion(num_classes, std::vector<int>(num_classes, 0));

    // 2. 混同行列の作成
    for (size_t i = 0; i < y_true.size(); ++i) {
        int true_id = label_to_id[y_true[i]];
        int pred_id = label_to_id[y_pred[i]];
        confusion[true_id][pred_id]++;
    }

    // 3. 間違いペア集計
    std::vector<std::pair<std::pair<int, int>, int>> errors;
    for (int i = 0; i < num_classes; ++i) {
        for (int j = 0; j < num_classes; ++j) {
            if (i != j && confusion[i][j] > 0) {
                errors.push_back({{i, j}, confusion[i][j]});
            }
        }
    }

    std::sort(errors.begin(), errors.end(), [](const auto& a, const auto& b) {
        return a.second > b.second;
    });

    std::cout << "Top 10 Confused Class Pairs:\n";
    for (int i = 0; i < std::min(10, (int)errors.size()); ++i) {
        auto& pair = errors[i];
        std::cout << "(" << id_to_label[pair.first.first] << ", " 
                  << id_to_label[pair.first.second] << "): " 
                  << pair.second << "\n";
    }
}
std::vector<std::string> y_true = {"100_えび", "200_さば", "100_えび", "300_いか"};
std::vector<std::string> y_pred = {"200_さば", "200_さば", "100_えび", "100_えび"};

print_top_confused_pairs(y_true, y_pred);

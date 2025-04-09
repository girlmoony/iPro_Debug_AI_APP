#include <iostream>
#include <fstream>
#include <vector>
#include <string>
#include <iomanip>
#include <cmath>

using namespace std;

// 構造体：画像識別の1件分の推論結果
struct PredictionResult {
    string order_id;          // 画像名または注文番号
    string true_label;        // 注文メニュー（正解）
    
    int top1_id;
    string top1_label;
    double top1_prob;
    
    int top2_id;
    string top2_label;
    double top2_prob;

    double confidence_threshold = 0.6;

    // Top1 と Top2 の確率差
    double getMargin() const {
        return abs(top1_prob - top2_prob);
    }

    // Top1 が正解か？
    bool isCorrect() const {
        return top1_label == true_label;
    }

    // 確信度が低いか（Top1の確率が閾値未満）
    bool isLowConfidence() const {
        return top1_prob < confidence_threshold;
    }
};

// CSVファイル出力関数
void exportPredictionsToCSV(const vector<PredictionResult>& results, const string& filename) {
    ofstream file(filename);
    if (!file.is_open()) {
        cerr << "ファイルを開けませんでした: " << filename << endl;
        return;
    }

    // ヘッダー
    file << "注文番号,注文メニュー,Top1クラスID,Top1クラス名,Top1確率,Top2クラスID,Top2クラス名,Top2確率,Top1とTop2差分,正誤フラグ,判定困難フラグ\n";

    // 本体
    for (const auto& result : results) {
        file << result.order_id << ","
             << result.true_label << ","
             << result.top1_id << ","
             << result.top1_label << ","
             << fixed << setprecision(4) << result.top1_prob << ","
             << result.top2_id << ","
             << result.top2_label << ","
             << fixed << setprecision(4) << result.top2_prob << ","
             << fixed << setprecision(4) << result.getMargin() << ","
             << (result.isCorrect() ? "1" : "0") << ","
             << (result.isLowConfidence() ? "1" : "0") << "\n";
    }

    file.close();
    cout << "CSVファイルを出力しました: " << filename << endl;
}

// テスト用のmain関数（モデル推論結果を模擬）
int main() {
    vector<PredictionResult> results = {
        {"IMG001", "唐揚げ弁当", 12, "唐揚げ弁当", 0.88, 34, "焼肉弁当", 0.06},
        {"IMG002", "焼肉弁当",   34, "焼肉弁当",   0.55, 12, "唐揚げ弁当", 0.40},
        {"IMG003", "ハンバーグ", 17, "ハンバーガー", 0.48, 18, "ハンバーグ", 0.46}
    };

    exportPredictionsToCSV(results, "image_predictions.csv");

    return 0;
}

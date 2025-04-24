#include <iostream>
#include <thread>
#include <unistd.h>
#include <sys/timerfd.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
//#include <experimental/filesystem>
#include <fstream>
#include <sstream>
#include <random>
#include <vector>
#include <algorithm>
#include <iostream>
#include <exception>
#define ADAM_APP_DEBUG_ENABLE 1
#include "AdamApi.h"
#include "AdamDebug.h"
#include "AI.h"
#include "params.h"
#include "APCTestApp_categoryMap.hpp"
#include "APCTestApp_top2_threshold_modifing.hpp"
namespace fs = std::filesystem;
//namespace fs = std::experimental::filesystem;
#define TIMERFD_INTERVAL_TIME   3
#define KEEP_ALIVE_TIME         5
#define APC_COMPARISON_RESULT_OK    0
#define APC_COMPARISON_RESULT_NG    1
#define NETA_CLASS_NUM 191
#define CHECK_IDX  8

extern int s_pipefd_for_stop[2];

APCTestAppTop2Threshold::APCTestAppTop2Threshold()
    : m_exitFlag(false), m_timerfd(-1), m_thread(nullptr) {
    InitDefaultMonitorInfo();
    InitDefaultOrderInfo();
    for (int i = 0; i < NETA_CLASS_NUM; i++) {  
        learned_sushi.push_back(class_info_recognize.at(i).class_code);
    }
    sprintf(csvPath, "%s/%s", ADAM_GetAppDataDirPath(), csv_dir_base);
    sprintf(imgDirBase, "%s/%s", ADAM_GetAppDataDirPath(), img_dir_base);
    sprintf(configPath, "%s/%s", ADAM_GetAppDataDirPath(), config_file);
    char *sdcardPath;
    if (from_sdcard) {  
        ADAM_GetSdCardPath(&sdcardPath);
        sprintf(imgDirBase, "%s/%s", sdcardPath, img_dir_base);
        sprintf(csvPath, "%s/%s", sdcardPath, csv_dir_base);
        sprintf(configPath, "%s/%s", sdcardPath, config_file);
    }
}
APCTestAppTop2Threshold::~APCTestAppTop2Threshold() {
    stop();
    join();
}
void APCTestAppTop2Threshold::start() {
    initPostProcessChain();
    m_thread = new std::thread(&APCTestAppTop2Threshold::run, this);
}
void APCTestAppTop2Threshold::stop() {
    m_exitFlag = true;
}
void APCTestAppTop2Threshold::join() {
    if (m_thread && m_thread->joinable()) {
        m_thread->join();
        delete m_thread;
        m_thread = nullptr;
    }
}
Config APCTestAppTop2Threshold::loadConfig(const std::string& filepath, ConfigType type) {
    std::ifstream infile(filepath);
    std::string line;
    while (std::getline(infile, line)) {
        switch (type) {
            case ConfigType::top1_thresh:
                if (line.find("THRESHOLD_TOP1=") == 0) {
                    m_config.threshold_top1 = std::stof(line.substr(strlen("THRESHOLD_TOP1=")));
                }
                break;
            case ConfigType::top2_thresh:
                if (line.find("THRESHOLD_TOP2=") == 0) {
                    m_config.threshold_top2 = std::stof(line.substr(strlen("THRESHOLD_TOP2=")));              
                }
                break;
             case ConfigType::diff_thresh:
                if (line.find("THRESHOLD_DIFF=") == 0) {
                    m_config.diff_threshold = std::stof(line.substr(strlen("THRESHOLD_DIFF=")));    
                }
                break;
            case ConfigType::topk_thresh:
                if (line.find("THRESHOLD_TOPK=") == 0) {
                    m_config.topK_threshold = std::stof(line.substr(strlen("THRESHOLD_TOPK=")));                      
                }
                break;              
            case ConfigType::PostProcessing:
                if (line.find("POST_PROCESS_ENABLE=") == 0) {
                    std::string flagStr = line.substr(strlen("POST_PROCESS_ENABLE="));
                    if (flagStr.length() == 8 && flagStr.find_first_not_of("01") == std::string::npos) {
                        m_config.post_process_flags = std::stoi(flagStr, nullptr, 2);
                    }
                }
                break;
        }
    }
    return m_config;
}
const ORDER_DATA& APCTestAppTop2Threshold::getOrderData(const std::string& line) {
    std::stringstream ss(line);
    std::string item;
    std::string lane;
    std::string menu_catecogy;
    ORDER_DATA order_data_row;
    int i = 0;
    while(getline(ss, item, ',')) {
        switch (i) {
            case 1:
                order_data_row.order_no = stoi(item);
                break;
            case 2:
                order_data_row.lane_no = stoi(item);
                break;
            case 3:
                order_data_row.seat_no = stoi(item);
                break;
            case 4:
                order_data_row.type = stoi(item);
                break;
            case 6:
                order_data_row.amount = stoi(item);
                break;
            case 8:
                order_data_row.tcommodity_cd = stoi(item);
                break;
            case 10:
                order_data_row.o_c = item;
                order_data_row.o_c.pop_back();//maybe to delete ','
                break;
            default:
                break;
        }
        i++;
    }        
    if ((order_data_row.lane_no == 1)) {
        lane = "A";
    } else if ((order_data_row.lane_no == 2)) {
        lane = "B";
    } else if ((order_data_row.lane_no == 3)) {
        lane = "C";
    }
    if ((order_data_row.type == 0) || (order_data_row.type == 4)) {
        menu_catecogy = "side";
    } else if ((order_data_row.type == 3) || (order_data_row.type == 7)) {
        menu_catecogy = "dessert";
    } else if ((order_data_row.type == 1)) {
        menu_catecogy = "nigiri";
    } else if ((order_data_row.type == 2)) {
        menu_catecogy = "gunkan";
    } else if ((order_data_row.type == 5) || (order_data_row.type == 6)) {
        ADAM_DEBUG_PRINT(ADAM_LV_INF, "drink order\n");
        return order_data_row;
    }
    if (order_data_row.o_c == "c") {
        ADAM_DEBUG_PRINT( ADAM_LV_INF, "o_c matched\n");          
        countor[lane][menu_catecogy]["deletecount"] += 1;  
        // m_orders.push_back(order_data_row);
    }else{
        ADAM_DEBUG_PRINT( ADAM_LV_INF, "o_c not match\n");
        countor[lane][menu_catecogy]["ordercount"] += 1;
        ADAM_DEBUG_PRINT(ADAM_LV_INF, "add monitor info\n");
        monitor_info[lane][menu_catecogy]["ORDER_NO"].push_back(order_data_row.order_no);
        monitor_info[lane][menu_catecogy]["SEAT_NO"].push_back(order_data_row.seat_no);
        monitor_info[lane][menu_catecogy]["TCOMMODITY_CD"].push_back(order_data_row.type);
        monitor_info[lane][menu_catecogy]["AMOUNT"].push_back(order_data_row.amount_no);    
    }
    ADAM_DEBUG_PRINT(ADAM_LV_INF, "get order\n");
    return order_data_row;
}
std::pair<std::string, std::string> APCTestAppTop2Threshold::getLaneMenuCate(const ORDER_DATA& order_data_row) {
    if ((order_data_row.lane_no == 1)) {
        lane = "A";
    } else if ((order_data_row.lane_no == 2)) {
        lane = "B";
    } else if ((order_data_row.lane_no == 3)) {
        lane = "C";
    }
    if ((order_data_row.type == 0) || (order_data_row.type == 4)) {
        menu_catecogy = "side";
    } else if ((order_data_row.type == 3) || (order_data_row.type == 7)) {
        menu_catecogy = "dessert";
    } else if ((order_data_row.type == 1)) {
        menu_catecogy = "nigiri";
    } else if ((order_data_row.type == 2)) {
        menu_catecogy = "gunkan";
    } else if ((order_data_row.type == 5) || (order_data_row.type == 6)) {
        ADAM_DEBUG_PRINT(ADAM_LV_INF, "drink order\n");
    }
    return{lane, menu_catecogy};
}
bool APCTestAppTop2Threshold::isTrainedOrder(std::string lane, std::string menu_catecogy, int p_code) {
    ADAM_DEBUG_PRINT(ADAM_LV_INF, "p_code[%d].\n", p_code);    
    bool ret = false;
    auto it = std::find(learned_sushi.begin(), learned_sushi.end(), p_code);
    if (it != learned_sushi.end()){
        ADAM_DEBUG_PRINT(ADAM_LV_INF, "it[%d].\n", *it);
        countor[lane][menu_catecogy]["netaRecongnitionCount"] += 1;
        ret = true;
    } else {
        ADAM_DEBUG_PRINT( ADAM_LV_INF, "no matched learned_sushi\n");
        countor[lane][menu_catecogy]["notLearnedCount"] += 1;
        ret = false;        
    }
    return ret;
}
int APCTestAppTop2Threshold::load_dummy_image(const char *file_name) {
    char path[512];
    sprintf(path, "%s/%s", imgDir, file_name);
    // ADAM_DEBUG_PRINT(ADAM_LV_INF, "dummy path:%s\n", file_name);
    OutputLog(std::string(file_name));
    FILE *fp = fopen(path, "rb");
    if(fp != NULL) {
        fread(img_p, 1, READ_IMG_BYTE_SIZE, fp);
        // fread(img_p, 1, IMG_YUV_SIZE, fp);
        fclose(fp);
    } else {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "fopen err! path:%s\n", path);
        return 1;
    }
    return 0;
}
bool APCTestAppTop2Threshold::selectTestImage(const int category) {
    bool ret = false;
    LABEL_DATA label_data_row = commodity_info.at(category);
    sprintf(imgDir, "%s/%s", imgDirBase, label_data_row.label_name.c_str());
    std::vector<std::string> fileList;
    DIR *dp;
    struct dirent *dirp;
    if ((dp = opendir(imgDir)) == NULL) {
        ADAM_DEBUG_PRINT( ADAM_LV_INF, "Error opening:%s\n", imgDir);
        return ret;
    } else {
        while ((dirp = readdir(dp)) != NULL) {
            if (dirp->d_name[0] != '.') {
                // fileList.push_back(std::string(imgDir) + "/" + std::string(dirp->d_name));
                fileList.push_back(std::string(dirp->d_name));
            }
        }
        closedir(dp);
    }
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<size_t> dist(0, fileList.size() -1);
    size_t randomIndex = dist(gen);
    std::string randomFile = fileList[randomIndex];
    ADAM_DEBUG_PRINT( ADAM_LV_INF, "imgDir: %s, d_name: %s\n", imgDir, randomFile.c_str());
    res = load_dummy_image(randomFile.c_str());
    if (res != 0) {
        ADAM_DEBUG_PRINT( ADAM_LV_INF, "error load image.\n");
        OutputLog("error load image.\n");
        return ret;
    }
    return true;
}
const std::vector<std::pair<float, E_Class>> APCTestAppTop2Threshold::getTopKPredictions(
    const std::vector<float>& scores, int k, float threshold, const std::map<int, E_Class>& class_info_recognize) {
    std::vector<std::pair<float, E_Class>> filtered;
    std::vector<std::pair<float, E_Class>> temp;
    for (size_t i = 0; i < scores.size(); ++i) {
        temp.emplace_back(scores[i], static_cast<int>(i));
    }
    std::sort(temp.begin(), temp.end(),
              [](const auto& a, const auto& b) { return a.first > b.first; });
    if (k > 0) {
        if (static_cast<int>(temp.size()) > k) {
            temp.resize(k);
        }
    } else {
        temp.erase(
            std::remove_if(temp.begin(), temp.end(),
                           [threshold](const auto& p) { return p.first < threshold; }),
            temp.end()
        );
    }
    for (const auto& [score, idx] : temp) {
        auto it = class_info_recognize.find(idx);
        if (it != class_info_recognize.end()) {
            filtered.emplace_back(score, it->second);
        }
    }
    return filtered;
}

PostProcessResult APCTestAppTop2Threshold::evaluateMissedPrediction(
    const std::string& lane,
    const std::string& menu_category,
    int predicted_class,
    const std::vector<int>& valid_seat_list,
    const std::map<std::string, std::map<std::string, std::vector<int>>>& monitor_info,
    bool isTop1)
{
    for (const std::string& item : {"nigiri", "gunkan", "side", "dessert"}) {
        const auto& class_list = monitor_info.at(lane).at(item).at("TCOMMODITY_CD");
        auto it = std::find(class_list.begin(), class_list.end(), predicted_class);
        if (it != class_list.end()) {
            int idx = std::distance(class_list.begin(), it);
            int predicted_seat = monitor_info.at(lane).at(item).at("SEAT_NO")[idx];
            if (isTopPredictionAcceptable(predicted_seat, valid_seat_list)) {
                return isTop1 ? PostProcessResult::TOP1_FALSE_START : PostProcessResult::TOP2_FALSE_START;
            } else {
                return isTop1 ? PostProcessResult::TOP1_MANUAL : PostProcessResult::TOP2_MANUAL;
            }
        }
    }
    return isTop1 ? PostProcessResult::TOP1_MANUAL : PostProcessResult::TOP2_MANUAL;
}


PostProcessResult APCTestAppTop2Threshold::processTop1Judge(
    const ORDER_DATA& order,
    const std::vector<std::pair<float, E_Class>>& topK,
    const std::vector<int>& valid_seat_list,
    const std::map<std::string, std::map<std::string, std::vector<int>>>& monitor_info)
{
    if (topK.empty()) return PostProcessResult::NO_HIT;

    const auto& [lane, menu_category] = getLaneMenuCate(order);

    if (topK[0].second.class_code == order.tcommodity_cd) {
        return PostProcessResult::TOP1_CORRECT;
    }

    return evaluateMissedPrediction(
        lane, menu_category,
        topK[0].second.class_code,
        valid_seat_list,
        monitor_info,
        true
    );
}

PostProcessResult APCTestAppTop2Threshold::processTop2Judge(
    const ORDER_DATA& order,
    const std::vector<std::pair<float, E_Class>>& topK,
    const std::vector<int>& valid_seat_list,
    const std::map<std::string, std::map<std::string, std::vector<int>>>& monitor_info)
{
    if (topK.empty()) return PostProcessResult::NO_HIT;

    const auto& [lane, menu_category] = getLaneMenuCate(order);

    // Step 1: Top1正解
    if (topK[0].second.class_code == order.tcommodity_cd) {
        return PostProcessResult::TOP1_CORRECT;
    }

    // Step 2: Top1が不正解 → 誤出発 or 手動
    PostProcessResult top1_result = evaluateMissedPrediction(
        lane, menu_category,
        topK[0].second.class_code,
        valid_seat_list,
        monitor_info,
        true);

    // Top1が完全誤出発と判定された場合はそれで終了
    if (top1_result == PostProcessResult::TOP1_FALSE_START) return top1_result;

    // Step 3: Top2正解判定
    if (topK.size() > 1 && topK[1].second.class_code == order.tcommodity_cd) {
        return PostProcessResult::TOP2_CORRECT;
    }

    // Step 4: Top2誤出発 or 手動
    return evaluateMissedPrediction(
        lane, menu_category,
        topK[1].second.class_code,
        valid_seat_list,
        monitor_info,
        false);
}


PostProcessResult APCTestAppTop2Threshold::processTop2ThreshJudge(
    const ORDER_DATA& order,
    const std::vector<std::pair<float, E_Class>>& topK,
    const std::vector<int>& valid_seat_list,
    const std::map<std::string, std::map<std::string, std::vector<int>>>& monitor_info)
{
    if (topK.empty()) return PostProcessResult::NO_HIT;

    const auto& [lane, menu_category] = getLaneMenuCate(order);

    if (topK[0].second.class_code == order.tcommodity_cd) {
        return PostProcessResult::TOP1_CORRECT;
    }

    PostProcessResult top1_result = evaluateMissedPrediction(
        lane, menu_category,
        topK[0].second.class_code,
        valid_seat_list,
        monitor_info,
        true);

    if (top1_result == PostProcessResult::TOP1_FALSE_START) return top1_result;

   // Top2 not exist
   if (topK.size() <= 1) return PostProcessResult::TOP2_MANUAL;

   // Top2 閾値チェック
   if (topK[1].first < m_config.threshold_top2){
       return PostProcessResult::TOP2_MANUAL;
   }else{
       if (topK[1].second.class_code == order.tcommodity_cd) {
           return PostProcessResult::TOP2_THRESH_CORRECT;
       }else {
           // Top2も不正解 → 誤出発 or 手動
           return evaluateMissedPrediction(
               lane, menu_category,
               topK[1].second.class_code,
               valid_seat_list,
               monitor_info,
               false);
       }

   }

}

PostProcessResult APCTestApp::processScoreGapJudge(
        const ORDER_DATA& order,
        const std::vector<std::pair<float, E_Class>>& topK,
        const std::vector<int>& valid_seat_list,
        const std::map<std::string, std::map<std::string, std::vector<int>>>& monitor_info)
    {
        if (topK.size() < 2) return PostProcessResult::NO_HIT;
    
        const auto& [lane, menu_category] = getLaneMenuCate(order);
    
        const int top1_class = topK[0].second.class_code;
        const int top2_class = topK[1].second.class_code;
        const float top1_score = topK[0].first;
        const float top2_score = topK[1].first;
        const float score_diff = top1_score - top2_score;
    
        if (top1_class == order.tcommodity_cd) {
            return PostProcessResult::TOP1_CORRECT;
        }
    
        PostProcessResult top1_result = evaluateMissedPrediction(
            lane, menu_category,
            topK[0].second.class_code,
            valid_seat_list,
            monitor_info,
            true);
    
        if (top1_result == PostProcessResult::TOP1_FALSE_START) return top1_result;
     
    
        if (score_diff > m_config.diff_threshold) { 
            return PostProcessResult::TOP1_MANUAL;
        }
    
        if (top2_class == order.tcommodity_cd) {
            return PostProcessResult::DIFF_THRESH_CORRECT;
        } else {
            return evaluateMissedPrediction(
                lane, menu_category,
                top2_class,
                valid_seat_list,
                monitor_info,
                false);
        }
    }
}

PostProcessResult APCTestApp::processScoreGapJudge(
        const ORDER_DATA& order,
        const std::vector<std::pair<float, E_Class>>& topK,
        const std::vector<int>& valid_seat_list,
        const std::map<std::string, std::map<std::string, std::vector<int>>>& monitor_info)
    {
        if (topK.size() < 2) return PostProcessResult::NO_HIT;
    
        const auto& [lane, menu_category] = getLaneMenuCate(order);
    
        const int top1_class = topK[0].second.class_code;
        const int top2_class = topK[1].second.class_code;
        const float top1_score = topK[0].first;
        const float top2_score = topK[1].first;
        const float score_diff = top1_score - top2_score;
    
        if (top1_class == order.tcommodity_cd) {
            return PostProcessResult::TOP1_CORRECT;
        }
    
        PostProcessResult top1_result = evaluateMissedPrediction(
            lane, menu_category,
            topK[0].second.class_code,
            valid_seat_list,
            monitor_info,
            true);
    
        if (top1_result == PostProcessResult::TOP1_FALSE_START) return top1_result;
     
    
        if (score_diff > m_config.diff_threshold) { 
            return PostProcessResult::TOP1_MANUAL;
        }
    
        if (top2_class == order.tcommodity_cd) {
            return PostProcessResult::DIFF_THRESH_CORRECT;
        } else {
            return evaluateMissedPrediction(
                lane, menu_category,
                top2_class,
                valid_seat_list,
                monitor_info,
                false);
        }
    }
}



PostProcessResult APCTestAppTop2Threshold::processTopKAboveThreshJudge(
    const ORDER_DATA& order,
    const std::vector<std::pair<float, E_Class>>& topK,
    const std::vector<int>&,
    const std::map<std::string, std::map<std::string, std::vector<int>>>&)
{
    for (const auto& [score, e_class] : topK) {
        if (score >= m_config.topK_threshold && e_class.class_code == order.tcommodity_cd) {
            return PostProcessResult::TOP1_CORRECT;
        }
    }
    return PostProcessResult::NO_HIT;
}

PostProcessResult APCTestApp::processTopKAboveThreshJudge(
    const ORDER_DATA& order,
    const std::vector<std::pair<float, E_Class>>& topK,
    const std::vector<int>& valid_seat_list,
    const std::map<std::string, std::map<std::string, std::vector<int>>>& monitor_info)
{
    if (topK.empty()) return PostProcessResult::NO_HIT;

    const auto& [lane, menu_category] = getLaneMenuCate(order);

    int rank = 1;

    for (const auto& [score, e_class] : topK) {
        // ⛔️ スコアが閾値未満 → 以降はすべて無視し、手動
        if (score < m_config.topK_threshold) {
            return (rank == 1) ? PostProcessResult::TOP1_MANUAL : PostProcessResult::TOP2_MANUAL;
        }

        const int candidate_class = e_class.class_code;

        // ✅ 正解
        if (candidate_class == order.tcommodity_cd) {
            return (rank == 1) ? PostProcessResult::TOP1_THRESH_CORRECT : PostProcessResult::TOP2_THRESH_CORRECT;
        }

        // ❌ 不正解 → 誤出発判定
        const PostProcessResult result = evaluateMissedPrediction(
            lane, menu_category,
            candidate_class,
            valid_seat_list,
            monitor_info,
            rank == 1);

        if ((rank == 1 && result == PostProcessResult::TOP1_FALSE_START) ||
            (rank >= 2 && result == PostProcessResult::TOP2_FALSE_START)) {
            return result;
        }

        // 手動はループ後にまとめて対応
        rank++;
    }

    // 全部外れた場合 → 最後は手動
    return PostProcessResult::TOP2_MANUAL;
}


PostProcessResult APCTestApp::processTop1ThreshJudge(
    const ORDER_DATA& order,
    const std::vector<std::pair<float, E_Class>>& topK,
    const std::vector<int>& valid_seat_list,
    const std::map<std::string, std::map<std::string, std::vector<int>>>& monitor_info)
{
    if (topK.empty()) return PostProcessResult::NO_HIT;

    const auto& [lane, menu_category] = getLaneMenuCate(order);

    const int top1_class = topK[0].second.class_code;
    const float top1_score = topK[0].first;

    if (top1_class == order.tcommodity_cd && top1_score >= m_config.threshold_top1) {
        return PostProcessResult::TOP1_CORRECT;
    }

    // Top1が不正解またはスコア不足 → 誤出発 or 手動判定
    return evaluateMissedPrediction(
        lane, menu_category,
        top1_class,
        valid_seat_list,
        monitor_info,
        true);
}


void APCTestAppTop2Threshold::updateEvaluationCounters(
    int lane,
    const std::string& menu_category,
    int top1_class,
    float top1_score,
    float top2_score,
    const std::vector<int>& valid_seat_list,
    const std::map<std::string, std::map<std::string, std::vector<int>>>& monitor_info,
    std::map<int, std::map<std::string, std::map<std::string, int>>>& countor)
{
   
}

std::vector<PostProcessFunc> postProcessChain;

void APCTestAppTop2Threshold::initPostProcessChain() {
    postProcessChain = {
        std::bind(&APCTestAppTop2Threshold::processTop1Judge, this,
            std::placeholders::_1, std::placeholders::_2, std::placeholders::_3, std::placeholders::_4),

        std::bind(&APCTestAppTop2Threshold::processTop2Judge, this,
            std::placeholders::_1, std::placeholders::_2, std::placeholders::_3, std::placeholders::_4),

        std::bind(&APCTestAppTop2Threshold::processTop2ThreshJudge, this,
            std::placeholders::_1, std::placeholders::_2, std::placeholders::_3, std::placeholders::_4),

        std::bind(&APCTestAppTop2Threshold::processScoreGapJudge, this,
            std::placeholders::_1, std::placeholders::_2, std::placeholders::_3, std::placeholders::_4),

        std::bind(&APCTestAppTop2Threshold::processTopKAboveThreshJudge, this,
            std::placeholders::_1, std::placeholders::_2, std::placeholders::_3, std::placeholders::_4),

        std::bind(&APCTestAppTop2Threshold::processTop1ThreshJudge, this,
            std::placeholders::_1, std::placeholders::_2, std::placeholders::_3, std::placeholders::_4)
    };
}


void APCTestAppTop2Threshold::handleInferenceResult(const std::vector<Rect>& rect_vec, const ORDER_DATA& order) {
    if (rect_vec.empty() || rect_vec[0].p_confidence_l == nullptr) return;

    const float* conf = rect_vec[0].p_confidence_l;
    std::vector<float> confidence_vec(conf, conf + NETA_CLASS_NUM);

    auto topK = getTopKPredictions(confidence_vec, 5, 0.0f, class_info_recognize);
    if (topK.empty()) return;

    int top1_class = topK[0].second.class_code;
    float top1_score = topK[0].first;
    float top2_score = (topK.size() > 1) ? topK[1].first : 0.0f;

    auto [lane, menu_category] = getLaneMenuCate(order);
    std::vector<int> valid_seats = set_lane_seat_no(lane, order.seat_no);

    Config cfg = loadConfig(configPath, ConfigType::PostProcessing);

    for (size_t i = 0; i < postProcessChain.size(); ++i) {
        if ((cfg.post_process_flags >> i) & 1) {
            PostProcessResult result = postProcessChain[i](
                order, topK, valid_seats, monitor_info);
    
                switch (result) {
                    case PostProcessResult::TOP1_CORRECT:
                        countor[lane][menu_category]["TOP1正解数"]++; break;
                    case PostProcessResult::TOP2_CORRECT:
                    case PostProcessResult::TOP2_THRESH_CORRECT:
                        countor[lane][menu_category]["TOP2正解数"]++; break;
                    case PostProcessResult::TOP1_FALSE_START:
                        countor[lane][menu_category]["TOP1誤出発数"]++; break;
                    case PostProcessResult::TOP1_MANUAL:
                        countor[lane][menu_category]["TOP1手動数"]++; break;
                    case PostProcessResult::TOP2_FALSE_START:
                        countor[lane][menu_category]["TOP2誤出発数"]++; break;
                    case PostProcessResult::TOP2_MANUAL:
                        countor[lane][menu_category]["TOP2手動数"]++; break;
                    default:
                        countor[lane][menu_category]["TOP1手動数"]++; break;
                }
        }
    }
    
    // 該当なし → 手動とみなす（TOP1 or TOP2？用途に応じて）
    countor[lane][menu_category]["TOP2手動数"]++;
}

void APCTestApp::runInference(const ORDER_DATA& order) {
    if (!selectTestImage(order.tcommodity_cd)) return;

    _pAi->initializePredict();
    _pAi->set_image_for_APC(img_p);
    std::vector<Rect> rect_vec = _pAi->recognition_sushi();

    handleInferenceResult(rect_vec, order);  // 1皿分の処理とカウント
}

void APCTestApp::runInferenceForMulti(const ORDER_DATA& order) {
    std::vector<PostProcessResult> dish_results;

    for (int i = 0; i < order.amount; ++i) {
        if (!selectTestImage(order.tcommodity_cd)) continue;

        _pAi->initializePredict();
        _pAi->set_image_for_APC(img_p);
        std::vector<Rect> rect_vec = _pAi->recognition_sushi();

        PostProcessResult result = handleInferenceAndReturnResult(rect_vec, order);  // 1皿分の結果だけ取得
        dish_results.push_back(result);
    }

    const auto& [lane, menu_category] = getLaneMenuCate(order);
    PostProcessResult final_result = PostProcessResult::TOP2_THRESH_CORRECT;

    for (const auto& r : dish_results) {
        if (r == PostProcessResult::TOP1_FALSE_START) {
            final_result = PostProcessResult::TOP1_FALSE_START;
            break;
        }
        if (r == PostProcessResult::TOP1_THRESH_CORRECT) {
            final_result = PostProcessResult::TOP1_THRESH_CORRECT;
        }
        else if (r == PostProcessResult::TOP2_FALSE_START &&
                 final_result != PostProcessResult::TOP1_THRESH_CORRECT) {
            final_result = PostProcessResult::TOP2_FALSE_START;
        }
        else if (r == PostProcessResult::TOP2_MANUAL &&
                 final_result != PostProcessResult::TOP1_THRESH_CORRECT &&
                 final_result != PostProcessResult::TOP2_FALSE_START) {
            final_result = PostProcessResult::TOP2_MANUAL;
        }
    }

    // カウント集計
    switch (final_result) {
        case PostProcessResult::TOP1_FALSE_START:
            countor[lane][menu_category]["TOP1誤出発数"]++; break;
        case PostProcessResult::TOP1_THRESH_CORRECT:
            countor[lane][menu_category]["TOP1正解数"]++; break;
        case PostProcessResult::TOP2_FALSE_START:
            countor[lane][menu_category]["TOP2誤出発数"]++; break;
        case PostProcessResult::TOP2_MANUAL:
            countor[lane][menu_category]["TOP2手動数"]++; break;
        case PostProcessResult::TOP2_THRESH_CORRECT:
            countor[lane][menu_category]["TOP2正解数"]++; break;
        default: break;
    }
}

void APCTestApp::handleInferenceResult(const std::vector<Rect>& rect_vec, const ORDER_DATA& order) {
    PostProcessResult result = handleInferenceAndReturnResult(rect_vec, order);

    const auto& [lane, menu_category] = getLaneMenuCate(order);

    switch (result) {
        case PostProcessResult::TOP1_THRESH_CORRECT:
            countor[lane][menu_category]["TOP1正解数"]++; break;
        case PostProcessResult::TOP1_FALSE_START:
            countor[lane][menu_category]["TOP1誤出発数"]++; break;
        case PostProcessResult::TOP1_MANUAL:
            countor[lane][menu_category]["TOP1手動数"]++; break;
        case PostProcessResult::TOP2_THRESH_CORRECT:
            countor[lane][menu_category]["TOP2正解数"]++; break;
        case PostProcessResult::TOP2_FALSE_START:
            countor[lane][menu_category]["TOP2誤出発数"]++; break;
        case PostProcessResult::TOP2_MANUAL:
            countor[lane][menu_category]["TOP2手動数"]++; break;
        default:
            break;
    }
}

PostProcessResult APCTestApp::handleInferenceAndReturnResult(
    const std::vector<Rect>& rect_vec,
    const ORDER_DATA& order)
{
    if (rect_vec.empty() || rect_vec[0].p_confidence_l == nullptr) return PostProcessResult::NO_HIT;

    std::vector<float> conf(rect_vec[0].p_confidence_l, rect_vec[0].p_confidence_l + NETA_CLASS_NUM);
    auto topK = getTopKPredictions(conf, 5, 0.0f, class_info_recognize);

    if (topK.empty()) return PostProcessResult::NO_HIT;

    auto [lane, menu_category] = getLaneMenuCate(order);
    std::vector<int> valid_seats = set_lane_seat_no(lane, order.seat_no);

    Config cfg = loadConfig(configPath, ConfigType::PostProcessing);

    for (size_t i = 0; i < postProcessChain.size(); ++i) {
        if ((cfg.post_process_flags >> i) & 1) {
            PostProcessResult result = postProcessChain[i](order, topK, valid_seats, monitor_info);
            if (result != PostProcessResult::NO_HIT) return result;
        }
    }

    return PostProcessResult::TOP1_MANUAL;
}

void APCTestAppTop2Threshold::runInference(const ORDER_DATA& order) {
    vector<Rect> rect_vec;
    vector<Rect> rect_vec_kuzure;
    vector<Rect> rect_vec_neta;
    if (!skip_detection_plate) {
       return;
    }    
    bool retGetDummyImage = selectTestImage(order.tcommodity_cd);
    if (!retGetDummyImage) {
        return;
    }
    if (!skip_detection_plate) {
        return;
    }
    _pAi->initializePredict();
    _pAi->set_image_for_APC(img_p);
    rect_vec_neta = _pAi->recognition_sushi();
    printSubString(rect_vec_neta[0].p_confidence_l, NETA_CLASS_NUM, "predict recognition_sushi");
    handleInferenceResult(rect_vec_neta, order);
    // updateEvaluationCounters(
    // lane,
    // menu_category,
    // top1_class,
    // top1_score,
    // top2_score,
    // order_lane_seat_no,
    // monitor_info,
    // countor
    // );
    return;
}
void APCTestAppTop2Threshold::runInferenceForMulti(const ORDER_DATA& order) {
    vector<Rect> rect_vec;
    vector<Rect> rect_vec_kuzure;
    vector<Rect> rect_vec_neta;
    if (!skip_detection_plate) {
       return;
    }
    int amount_no = order.amount;
    ADAM_DEBUG_PRINT(ADAM_LV_INF, "ordered dishes over 2\n");
    std::vector<int> each_dish_top1_pred_result;
    std::vector<int> each_dish_top2_pred_result;
    for (int j = 0; j < amount_no; j++) {
        int top2_check_flag = 0;
        bool retGetDummyImage = selectTestImage(order.tcommodity_cd);
        if (!retGetDummyImage) {
            continue;
        }
        _pAi->initializePredict();
        _pAi->set_image_for_APC(img_p);
        rect_vec_neta = _pAi->recognition_sushi();
        printSubString(rect_vec_neta[0].p_confidence_l, NETA_CLASS_NUM, "predict recognition_sushi");
        handleInferenceResult(rect_vec_neta, order);
    }
    // updateEvaluationCounters(
    //     lane,
    //     menu_category,
    //     top1_class,
    //     top1_score,
    //     top2_score,
    //     order_lane_seat_no,
    //     monitor_info,
    //     countor
    // );
    return;
}    
void APCTestAppTop2Threshold::run() {
    try {
        _pAi = new AI(1);
        _pAi->loadModel(
            AI::getInstallFileName(MODEL_TYPE_OBJECT_DETECTION),
            AI::getInstallFileName(MODEL_TYPE_IMG_CLASSIFICATION),
            AI::getInstallFileName(MODEL_TYPE_SUSHI_RECOGNITION)
        );

        std::ifstream file(csvPath);
        if (!file.is_open()) {
            ADAM_DEBUG_PRINT(ADAM_LV_ERR, "Failed to open CSV file: %s\n", csvPath.c_str());
            return;
        }

        std::string line;
        bool is_header = true;

        while (std::getline(file, line)) {
            if (is_header) {
                is_header = false;
                continue;
            }

            const ORDER_DATA& order_data_row = getOrderData(line);
            if (((order_data_row.o_c != "c") && (order_data_row.o_c != "o")) ||
                (order_data_row.type == 5 || order_data_row.type == 6)) {
                ADAM_DEBUG_PRINT(ADAM_LV_INF, "order skipped\n");
                continue;
            }

            auto [lane, menu_catecogy] = getLaneMenuCate(order_data_row);
            if (!isTrainedOrder(lane, menu_catecogy, order_data_row.tcommodity_cd)) {
                ADAM_DEBUG_PRINT(ADAM_LV_INF, "not trained order\n");
                continue;
            }

            if (order_data_row.amount > 1) {
                ADAM_DEBUG_PRINT(ADAM_LV_INF, "multidishes\n");
                runInferenceForMulti(order_data_row);
            } else if (order_data_row.amount == 1) {
                ADAM_DEBUG_PRINT(ADAM_LV_INF, "singledish\n");
                runInference(order_data_row);
            } else {
                ADAM_DEBUG_PRINT(ADAM_LV_ERR, "irregular case\n");
                continue;
            }
        }
    } catch (const std::exception& e) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "WorkThread exception: %s\n", e.what());
    } catch (...) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "Unknown exception in WorkThread.\n");
    }

    ADAM_DEBUG_PRINT(ADAM_LV_INF, "worker thread finished\n");
    write(s_pipefd_for_stop[1], "1", 1);
}

void APCTestAppTop2Threshold::OutputLog(std::string txt) {
    if (logPath == "") {
        char *imgPath;
        ADAM_GetSdCardPath(&imgPath);
        std::time_t now = std::time(nullptr);
        std::tm* timeinfo = std::localtime(&now);
        char buffer[14];
        std::strftime(buffer, sizeof(buffer), "%y%m%d%H%M%S", timeinfo);
        char log_path_c[512];
        sprintf(log_path_c, "%s/logs/app_inference_%s.log", imgPath, buffer);
        logPath = std::string(log_path_c);
    }
    ofstream outputfile(logPath, std::ios::app);
    outputfile << txt << endl;
    outputfile.close();
}
void APCTestAppTop2Threshold::printSubString(float* confidence, int l_size, const char* msg) {
    int num_sub = 4096;
    // int num_sub = 100;
    std::string s = "";
    for (int k = 0; k < l_size; k++) {
        s += std::to_string(confidence[k]);
        s += ",";
    }
    s.pop_back();
    int length = s.length();
    int start = 0;
    int end = num_sub;
    while (start < length) {
        if (end > length) {
            end = length;
        }
        std::string printMsg = std::string(msg) + " " + s.substr(start, end - start);
        OutputLog(printMsg);
        start += num_sub;
        end += num_sub;
    }
}
std::tuple<int, int, int> APCTestAppTop2Threshold::discrimination_order(vector<Rect> rect_vec, const std::map<int, E_Class>& classInfo, int orderJudgInfo, int out_max_idx, int pDiscriminationResult, int pComparisonResult)
{
   int max_idx = rect_vec[0].getMaxIndex();
    try{
        size_t arr_size = NETA_CLASS_NUM;
        auto [s_index, s_confidence] = getSecondLargest(rect_vec[0].p_confidence_l, arr_size);
        int secondDiscriminationResult = classInfo.at(s_index).class_code;
        int discriminationResult = classInfo.at(max_idx).class_code;
        pDiscriminationResult = discriminationResult;
        pComparisonResult = (orderJudgInfo == pDiscriminationResult ? APC_COMPARISON_RESULT_OK : APC_COMPARISON_RESULT_NG);
        ADAM_DEBUG_PRINT(ADAM_LV_INF, "discriminationResult[%d], orderJudgInfo[%d], pComparisonResult[%d], secondDiscriminationResult[%d].\n", discriminationResult, orderJudgInfo, pComparisonResult, secondDiscriminationResult);
        return std::make_tuple(pComparisonResult, discriminationResult, secondDiscriminationResult);
    } catch (const std::exception& e) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "Error getSecondLargest");
        return std::make_tuple(APC_COMPARISON_RESULT_NG, -1, -1);
    }
}
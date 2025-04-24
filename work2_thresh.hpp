#pragma once

#include <string>
#include <vector>
#include <map>
#include <functional>
#include <tuple>



class APCTestAppTop2Threshold {
    public:
        APCTestAppTop2Threshold();
        ~APCTestAppTop2Threshold();
        void start();
        void stop();
        void join();

// Forward declarations or include appropriate headers for these
struct ORDER_DATA;
struct Order;
struct Rect;
enum class E_Class;

// === Config Structure ===
struct Config {
    float threshold_top1 = 0.5f;
    float threshold_top2 = 0.4f;
    float diff_threshold = 0.2f;
    float topK_threshold = 0.1f;
    int post_process_flags = 15;
};

// === Counter Structure ===
struct Counter {
    int top1_correct_count = 0;
    int top2_correct_count = 0;
    int top2_thresh_correct_count = 0;
    int diff_thresh_correct_count = 0;
    int topK_threshold_count = 0;
    int top1_threshold_count = 0;
    int top1_false_trigger_count = 0;
    int other_false_trigger_count = 0;
    int manual_count = 0;
};

// === Config Type Enum ===
enum class ConfigType {
    top1_thresh,
    top2_thresh,
    diff_thresh,
    topk_thresh,
    PostProcessing
};

// === Post-Process Result Enum ===
enum class PostProcessResult {
    NO_HIT = 0,
    TOP1_CORRECT,
    TOP2_CORRECT,
    TOP2_THRESH_CORRECT,
    DIFF_THRESH_CORRECT,
    FALSE_TRIGGER,
    MANUAL,
    TOP1_FALSE_START,
    TOP1_MANUAL,
    TOP2_FALSE_START,
    TOP2_MANUAL
};

private:

// === Core Functions ===
void run();

bool isTrainedOrder(std::string lane, std::string menu_catecogy, int p_code);

std::pair<std::string, std::string> getLaneMenuCate(const ORDER_DATA& order_data_row);

Config loadConfig(const std::string& filepath, ConfigType type);

const ORDER_DATA& getOrderData(const std::string& line);

int load_dummy_image(const char* file_name);

bool selectTestImage(const int category);

const std::vector<std::pair<float, E_Class>> getTopKPredictions(
    const std::vector<float>& scores,
    int k,
    float threshold,
    const std::map<int, E_Class>& class_info_recognize);

void runInference(const Order& order);

void runInferenceForMulti(const Order& order);

void handleInferenceResult(const std::vector<Rect>& rect_vec, const Order& order);

void processTop1Judge(const std::vector<Rect>& rect_vec, const Order& order);

void processTop2Judge(const std::vector<Rect>& rect_vec, const Order& order);

void processTop2ThreshJudge(const std::vector<Rect>& rect_vec, const Order& order);

void processScoreGapJudge(const std::vector<Rect>& rect_vec, const Order& order);

void processTopKAboveThreshJudge(const std::vector<Rect>& rect_vec, const Order& order);

void processTop1ThreshJudge(const std::vector<Rect>& rect_vec, const Order& order);

void OutputLog(std::string txt);

void printSubString(float* confidence, int l_size, const char* msg);

std::tuple<int, int, int> discrimination_order(
    std::vector<Rect> rect_vec,
    const std::map<int, E_Class>& classInfo,
    int orderJudgInfo,
    int out_max_idx,
    int pDiscriminationResult,
    int pComparisonResult);

// === Global Variables ===
extern std::vector<int> learned_sushi;

// === Post Process Function Type ===
using PostProcessFunc = std::function<PostProcessResult(
    const ORDER_DATA& order,
    const std::vector<std::pair<float, E_Class>>& topK,
    const std::vector<int>& valid_seat_list,
    const std::map<std::string, std::map<std::string, std::vector<int>>>& monitor_info)>;


extern std::vector<PostProcessFunc> postProcessChain;
std::vector<int> learned_sushi;
    int check_idx = 8;
    char imgDirBase[256];
    char imgDir[256];
    char csvPath[256];
    char configPath[256];
    bool from_sdcard = true;
    char img_dir_base[] = "neta_simulation_images";
    char config_file[] = "config/config.txt";
    char csv_dir_base[] = "tenpo_info/OrderInfo_2551_2024-10-19.csv";
    bool genko_test = false;
    bool skip_detection_plate = true;
    const int READ_IMG_BYTE_SIZE = 196608;
    unsigned char img_p[READ_IMG_BYTE_SIZE];
    Config m_config;
    std::atomic<bool> m_exitFlag;
    int m_timerfd;
    std::thread* m_thread;
    AI* _pAi;
}// APCTESTAPP_TOP2_THRESHOLD_HPP
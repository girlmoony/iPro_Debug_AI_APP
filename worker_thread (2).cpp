#include "worker_thread.hpp"
#include <fstream>
#include <sstream>
#include <random>
#include <filesystem>

#include <iostream>
#include <thread>
#include <unistd.h>
#include <sys/timerfd.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include "AdamApi.h"
#include "AdamDebug.h"
namespace fs = std::filesystem;



#define TIMERFD_INTERVAL_TIME   3
#define KEEP_ALIVE_TIME         5

// コンストラクタ
WorkerThread::WorkerThread()
    : m_exitFlag(false), m_timerfd(-1), m_thread(nullptr), m_orderIndex(0) {} // ① 初期化追加

// run() のCSV読み込み後にチェック追加（④）
loadOrderCSV("orders/sample_orders.csv");
if (m_orders.empty()) {
    ADAM_DEBUG_PRINT(ADAM_LV_WRN, "No orders found. Exiting worker thread.\n");
    return;
}

WorkerThread::~WorkerThread() {
    stop();
    join();
}

void WorkerThread::start() {
    m_thread = new std::thread(&WorkerThread::run, this);
}

void WorkerThread::stop() {
    m_exitFlag = true;
}

void WorkerThread::join() {
    if (m_thread && m_thread->joinable()) {
        m_thread->join();
        delete m_thread;
        m_thread = nullptr;
    }
}

void WorkerThread::loadOrderCSV(const std::string& csvPath) {
    std::ifstream file(csvPath);
    if (!file.is_open()) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "Failed to open CSV file: %s\n", csvPath.c_str());
        return;
    }

    std::string line;
    while (std::getline(file, line)) {
        std::istringstream ss(line);
        std::string token;
        Order order;

        std::getline(ss, order.time, ',');
        std::getline(ss, order.seat, ',');
        std::getline(ss, order.lane, ',');
        std::getline(ss, token, ','); order.category = std::stoi(token);
        std::getline(ss, order.name, ',');
        std::getline(ss, token, ','); order.count = std::stoi(token);
        std::getline(ss, order.type, ',');

        if (order.type == "注文") {
            m_orders.push_back(order);
        }
    }

    ADAM_DEBUG_PRINT(ADAM_LV_INF, "Loaded %zu orders\n", m_orders.size());
}

std::string WorkerThread::selectTestImage(int category) {
    std::string categoryPath = "testdataset/" + std::to_string(category);
    std::vector<std::string> imageFiles;

    // selectTestImage() に exists チェック追加（③）
    if (!fs::exists(categoryPath)) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "Category path does not exist: %s\n", categoryPath.c_str());
        return "";
    }

    for (const auto& entry : fs::directory_iterator(categoryPath)) {
        if (entry.path().extension() == ".raw") {
            imageFiles.push_back(entry.path().string());
        }
    }

    if (imageFiles.empty()) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "No test images found in category %d\n", category);
        return "";
    }

    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, imageFiles.size() - 1);

    return imageFiles[dis(gen)];
}

void WorkerThread::runInference(const std::string& imagePath, const Order& order) {
    // NOTE: 後ほど ONNX Runtime に置き換え
    ADAM_DEBUG_PRINT(ADAM_LV_INF,
        "推論開始: カテゴリ[%d], 注文[%s], 座席[%s], レーン[%s], 画像[%s]\n",
        order.category, order.name.c_str(), order.seat.c_str(), order.lane.c_str(), imagePath.c_str());

    // 仮の推論結果を出力
    std::string predicted = "予測: 寿司カテゴリ" + std::to_string(order.category); // 仮の結果
    ADAM_DEBUG_PRINT(ADAM_LV_INF, "%s\n", predicted.c_str());
}


void WorkerThread::run() {
    m_timerfd = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC);
    if (m_timerfd == -1) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "timerfd_create() failed!\n");
        return;
    }

    struct itimerspec new_value;
    new_value.it_interval.tv_sec = TIMERFD_INTERVAL_TIME;
    new_value.it_interval.tv_nsec = 0;
    new_value.it_value.tv_sec = TIMERFD_INTERVAL_TIME;
    new_value.it_value.tv_nsec = 0;

    if (timerfd_settime(m_timerfd, 0, &new_value, NULL) == -1) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "timerfd_settime() failed!\n");
        close(m_timerfd);
        return;
    }

    T_ADAM_KEEPALIVE_ID keep_alive_id;
    if (ADAM_KeepAlive_Add(KEEP_ALIVE_TIME, &keep_alive_id) != ADAM_ERR_OK) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "ADAM_KeepAlive_Add() failed!\n");
        close(m_timerfd);
        return;
    }

    while (!m_exitFlag && m_orderIndex < m_orders.size()) {
        uint64_t data;
        int size = read(m_timerfd, &data, sizeof(data));
        // read() のdata未使用 suppress（⑤）
        (void)data;

        if (size != sizeof(data)) {
            ADAM_DEBUG_PRINT(ADAM_LV_ERR, "timerfd read error\n");
        }

        if (ADAM_KeepAlive_NotifyAlive(keep_alive_id) != ADAM_ERR_OK) {
            ADAM_DEBUG_PRINT(ADAM_LV_ERR, "ADAM_KeepAlive_NotifyAlive() failed!\n");
        }

        // 注文処理
        const Order& order = m_orders[m_orderIndex++];
        std::string imgPath = selectTestImage(order.category);
        if (!imgPath.empty()) {
            runInference(imgPath, order);
        }
    }


    ADAM_KeepAlive_Remove(keep_alive_id);
    close(m_timerfd);
}

#pragma once

#include <string>
#include <vector>
#include <thread>
#include <atomic>

class WorkerThread {
public:
    WorkerThread();
    ~WorkerThread();

    void start();
    void stop();
    void join();

private:
    void run();

    // === 追加部分 ===
    struct Order {
        std::string time;
        std::string seat;
        std::string lane;
        int category;
        std::string name;
        int count;
        std::string type; // "注文" or "消込"
    };

    void loadOrderCSV(const std::string& csvPath);
    std::string selectTestImage(int category);
    void runInference(const std::string& imagePath, const Order& order);

    std::vector<Order> m_orders;
    size_t m_orderIndex = 0;

    // === メンバ変数 ===
    std::atomic<bool> m_exitFlag;
    int m_timerfd;
    std::thread* m_thread;
};

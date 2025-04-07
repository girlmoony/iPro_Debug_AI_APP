#ifndef WORKER_THREAD_HPP
#define WORKER_THREAD_HPP

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
    std::atomic<bool> m_exitFlag;
    int m_timerfd;
    std::thread* m_thread;
};

#endif // WORKER_THREAD_HPP

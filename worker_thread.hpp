#ifndef WORKER_THREAD_HPP
#define WORKER_THREAD_HPP

#include <atomic>

class WorkerThread {
public:
    void run(std::atomic<bool>& exitFlag);
};

#endif // WORKER_THREAD_HPP

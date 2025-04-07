#include "worker_thread.hpp"
#include <iostream>
#include <unistd.h>

void WorkerThread::run(std::atomic<bool>& exitFlag) {
    while (!exitFlag) {
        std::cout << "=== Execute Thread No.1! ===\n";
        sleep(3);
    }
}

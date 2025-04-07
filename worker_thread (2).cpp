#include "worker_thread.hpp"
#include <iostream>
#include <thread>
#include <unistd.h>
#include <sys/timerfd.h>
#include <stdint.h>
#include <string.h>
#include <fcntl.h>
#include "AdamApi.h"
#include "AdamDebug.h"

#define TIMERFD_INTERVAL_TIME   3
#define KEEP_ALIVE_TIME         5

WorkerThread::WorkerThread()
    : m_exitFlag(false), m_timerfd(-1), m_thread(nullptr) {}

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

    while (!m_exitFlag) {
        uint64_t data;
        int size = read(m_timerfd, &data, sizeof(data));
        if (size != sizeof(data)) {
            ADAM_DEBUG_PRINT(ADAM_LV_ERR, "timerfd read error\n");
        }
        ADAM_DEBUG_PRINT(ADAM_LV_INF, "=== Execute Thread No.1! ===\n");

        if (ADAM_KeepAlive_NotifyAlive(keep_alive_id) != ADAM_ERR_OK) {
            ADAM_DEBUG_PRINT(ADAM_LV_ERR, "ADAM_KeepAlive_NotifyAlive() failed!\n");
        }
    }

    ADAM_KeepAlive_Remove(keep_alive_id);
    close(m_timerfd);
}

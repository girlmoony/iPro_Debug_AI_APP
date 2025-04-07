#include <iostream>
#include <thread>
#include <atomic>
#include <unistd.h>
#include <sys/epoll.h>
#include <sys/timerfd.h>
#include <fcntl.h>
#include <cstring>
#include <csignal>

extern "C" {
#include "AdamApi.h"
#include "AdamDebug.h"
}

#include "worker_thread.hpp"

#define MAX_EVENTS 2

static T_ADAM_EVENTLOOP_ID s_systemEventloopId = ADAM_INVALID_EVENTLOOP_ID;
static std::atomic<bool> s_exitFlag(false);
static int s_pipefd_for_stop[2];
static int s_timerfd = -1;

// プロトタイプ宣言
static void stop_handler(E_ADAM_STOP_FACTOR factor);
static void server_request_receive_handler(T_ADAM_REQUEST_ID requestId, ST_ADAM_NET_DATA* pData);
static void set_loop_exit();
static void proc_timer();
static int mainthread_main();

int main(int argc, char* argv[]) {
    E_ADAM_ERR err;
    ST_ADAM_SYSTEM_HANDLERS handlers;
    E_ADAM_START_FACTOR startFactor;
    int retFunc = -1;

    handlers.m_stopHandler = stop_handler;
    handlers.m_serverRequestReceiveHandler = server_request_receive_handler;
    handlers.m_notifyAppPrefUpdateHandler = nullptr;

    err = ADAM_Open(ADAM_APP_TYPE_FREE_STYLE, &handlers, &s_systemEventloopId, &startFactor);
    if (err != ADAM_ERR_OK) {
        return -1;
    }

    WorkerThread worker;
    worker.start();

    retFunc = mainthread_main();

    worker.stop();
    worker.join();

    ADAM_Close();
    return retFunc;
}

static int mainthread_main() {
    int retFunc = -1;

    int epollfd = epoll_create(MAX_EVENTS);
    if (epollfd == -1) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "epoll_create() failed!\n");
        return retFunc;
    }

    if (pipe(s_pipefd_for_stop) == -1) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "pipe() failed!\n");
        close(epollfd);
        return retFunc;
    }

    struct epoll_event ev;
    ev.events = EPOLLIN;
    ev.data.ptr = (void*)set_loop_exit;
    if (epoll_ctl(epollfd, EPOLL_CTL_ADD, s_pipefd_for_stop[0], &ev) == -1) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "epoll_ctl ADD stop pipe failed!\n");
        close(epollfd);
        return retFunc;
    }

    s_timerfd = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC);
    if (s_timerfd == -1) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "timerfd_create() failed!\n");
        close(epollfd);
        return retFunc;
    }

    struct itimerspec new_value = {};
    new_value.it_interval.tv_sec = 5;
    new_value.it_value.tv_sec = 5;
    if (timerfd_settime(s_timerfd, 0, &new_value, nullptr) == -1) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "timerfd_settime() failed!\n");
        close(s_timerfd);
        return retFunc;
    }

    ev.events = EPOLLIN;
    ev.data.ptr = (void*)proc_timer;
    if (epoll_ctl(epollfd, EPOLL_CTL_ADD, s_timerfd, &ev) == -1) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "epoll_ctl ADD timerfd failed!\n");
        close(s_timerfd);
        return retFunc;
    }

    struct epoll_event events[MAX_EVENTS];
    while (!s_exitFlag) {
        int ndfs = epoll_wait(epollfd, events, MAX_EVENTS, -1);
        if (ndfs == -1) break;

        for (int i = 0; i < ndfs; ++i) {
            void (*func)(void) = (void(*)(void))events[i].data.ptr;
            func();
            if (s_exitFlag) break;
        }
    }

    close(s_timerfd);
    close(s_pipefd_for_stop[0]);
    close(s_pipefd_for_stop[1]);
    close(epollfd);
    return 0;
}

static void set_loop_exit() {
    ADAM_DEBUG_PRINT(ADAM_LV_DBG, "set loop exit\n");
    s_exitFlag = true;
}

static void proc_timer() {
    uint64_t data;
    int size = read(s_timerfd, &data, sizeof(data));
    if (size != sizeof(data)) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "timerfd read error\n");
    }
    ADAM_DEBUG_PRINT(ADAM_LV_INF, "*** Execute Main Thread! ***\n");
}

static void stop_handler(E_ADAM_STOP_FACTOR factor) {
    ADAM_DEBUG_PRINT(ADAM_LV_DBG, "stop app ( factor = %d )\n", factor);
    write(s_pipefd_for_stop[1], "1", 1);
}

static void server_request_receive_handler(T_ADAM_REQUEST_ID requestId, ST_ADAM_NET_DATA* pData) {
    ST_ADAM_NET_DATA resData;
    resData.m_type = pData->m_type;
    resData.m_pData = pData->m_pData;
    resData.m_size = pData->m_size;

    E_ADAM_ERR ret = ADAM_ServerResponse_Send(requestId, ADAM_DEFAULT_FORMAT, &resData);
    if (ret != ADAM_ERR_OK) {
        ADAM_DEBUG_PRINT(ADAM_LV_ERR, "Server response send failed\n");
    }
}

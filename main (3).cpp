#include <iostream>
#include <string>
#include <cstring>
#include <cctype>
#include <cstdlib>
#include <unistd.h>
#include <sys/epoll.h>
#include <sys/timerfd.h>
#include <fcntl.h>
#include <stdint.h>
#include <atomic>
#include <thread>

extern "C" {
#include "AdamApi.h"
#include "AdamDebug.h"
}

#include "worker_thread.hpp"

T_ADAM_EVENTLOOP_ID s_systemEventloopId = ADAM_INVALID_EVENTLOOP_ID;
static std::atomic<bool> s_exitFlag(false);
static int s_pipefd_for_stop[2];
static int s_timerfd = -1;
char g_arg1[256] = {0};

#define MAX_EVENTS 2

void stop_handler(E_ADAM_STOP_FACTOR factor);
void server_request_receive_handler(T_ADAM_REQUEST_ID requestId, ST_ADAM_NET_DATA* pData);
void set_loop_exit();
void proc_timer();
int mainthread_main();
void response_by_original_format(T_ADAM_REQUEST_ID requestId, ST_ADAM_NET_DATA* pData);
void response_by_html(T_ADAM_REQUEST_ID requestId);

int main(int argc, char* argv[]) {
    if (argc > 1) {
        strncpy(g_arg1, argv[1], sizeof(g_arg1) - 1);
    }

    ST_ADAM_SYSTEM_HANDLERS handlers;
    handlers.m_stopHandler = stop_handler;
    handlers.m_serverRequestReceiveHandler = server_request_receive_handler;
    handlers.m_notifyAppPrefUpdateHandler = nullptr;

    E_ADAM_START_FACTOR startFactor;
    if (ADAM_Open(ADAM_APP_TYPE_FREE_STYLE, &handlers, &s_systemEventloopId, &startFactor) != ADAM_ERR_OK) {
        return -1;
    }

    int ret = pipe(s_pipefd_for_stop);
    if (ret == -1) return -1;

    WorkerThread worker;
    worker.start();

    int retFunc = mainthread_main();

    worker.stop();
    worker.join();

    ADAM_Close();
    return retFunc;
}

int mainthread_main() {
    int epollfd = epoll_create(MAX_EVENTS);
    if (epollfd == -1) return -1;

    struct epoll_event ev;
    ev.events = EPOLLIN;
    ev.data.ptr = (void*)set_loop_exit;
    epoll_ctl(epollfd, EPOLL_CTL_ADD, s_pipefd_for_stop[0], &ev);

    s_timerfd = timerfd_create(CLOCK_MONOTONIC, TFD_CLOEXEC);
    struct itimerspec new_value = {};
    new_value.it_interval.tv_sec = 5;
    new_value.it_value.tv_sec = 5;
    timerfd_settime(s_timerfd, 0, &new_value, nullptr);

    ev.events = EPOLLIN;
    ev.data.ptr = (void*)proc_timer;
    epoll_ctl(epollfd, EPOLL_CTL_ADD, s_timerfd, &ev);

    struct epoll_event events[MAX_EVENTS];
    while (!s_exitFlag) {
        int ndfs = epoll_wait(epollfd, events, MAX_EVENTS, -1);
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

void stop_handler(E_ADAM_STOP_FACTOR factor) {
    write(s_pipefd_for_stop[1], "1", 1);
}

void set_loop_exit() {
    s_exitFlag = true;
}

void proc_timer() {
    uint64_t data;
    read(s_timerfd, &data, sizeof(data));
    ADAM_DEBUG_PRINT(ADAM_LV_INF, "*** Execute Main Thread! ***\n");
}

void server_request_receive_handler(T_ADAM_REQUEST_ID requestId, ST_ADAM_NET_DATA* pData) {
    switch (pData->m_type) {
        case 0:
            response_by_html(requestId);
            break;
        default:
            response_by_original_format(requestId, pData);
            break;
    }
}

void response_by_original_format(T_ADAM_REQUEST_ID requestId, ST_ADAM_NET_DATA* pData) {
    char* outputData = (char*)malloc(4096);
    if (!outputData) return;

    memcpy(outputData, pData->m_pData, pData->m_size);
    outputData[pData->m_size] = '\0';

    for (char* p = outputData; *p; ++p) {
        if (isupper(*p)) *p = tolower(*p);
        else *p = toupper(*p);
    }

    ST_ADAM_NET_DATA resData;
    resData.m_type = pData->m_type;
    resData.m_pData = outputData;
    resData.m_size = pData->m_size;

    ADAM_ServerResponse_Send(requestId, ADAM_DEFAULT_FORMAT, &resData);
    free(outputData);
}

void response_by_html(T_ADAM_REQUEST_ID requestId) {
    char* htmlData = (char*)malloc(4096);
    char* outputData = (char*)malloc(4096);
    if (!htmlData || !outputData) return;

    int bodySize = 0;
    bodySize += sprintf(htmlData + bodySize, "<HTML>\n<HEAD><TITLE>Sample HTML</TITLE></HEAD>\n<BODY>\n");
    bodySize += sprintf(htmlData + bodySize, "Sample HTML<br>\n");
    bodySize += sprintf(htmlData + bodySize, "Arg = %s<br>\n", g_arg1);
    bodySize += sprintf(htmlData + bodySize, "</BODY>\n</HTML>\n");

    int size = 0;
    size += sprintf(outputData + size, "HTTP/1.1 200 OK\n");
    size += sprintf(outputData + size, "Content-Type: text/html\n");
    size += sprintf(outputData + size, "Content-Length: %d\n\n", bodySize);
    memcpy(outputData + size, htmlData, bodySize);
    size += bodySize;

    ST_ADAM_NET_DATA resData;
    resData.m_type = 0;
    resData.m_pData = outputData;
    resData.m_size = size;

    ADAM_ServerResponse_Send(requestId, ADAM_USER_DEFINED_FORMAT, &resData);
    free(htmlData);
    free(outputData);
}

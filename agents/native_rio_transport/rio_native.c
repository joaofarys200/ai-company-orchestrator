/*
 * JARVIS OS — Phase 23: Windows Registered I/O (RIO) Native C Implementation
 * High-performance batched UDP I/O extension.
 */

#define RIO_EXPORTS
#include "rio_native.h"
#include <stdio.h>
#include <stdlib.h>

#ifdef _WIN32

static RIO_EXTENSION_FUNCTION_TABLE g_rio = {0};
static bool g_rio_loaded = false;

/* WSAID_MULTIPLE_RIO: 8509e081-96dd-4005-b165-9e2ee8c79e3f */
static const GUID WSAID_MULTIPLE_RIO_VAL = {
    0x8509e081, 0x96dd, 0x4005,
    {0xb1, 0x65, 0x9e, 0x2e, 0xe8, 0xc7, 0x9e, 0x3f}
};

#ifndef SIO_GET_MULTIPLE_EXTENSION_FUNCTION_POINTER
#define SIO_GET_MULTIPLE_EXTENSION_FUNCTION_POINTER 0xC8000024
#endif

#ifndef WSA_FLAG_REGISTERED_IO
#define WSA_FLAG_REGISTERED_IO 0x0100
#endif

#ifndef RIO_MSG_DEFER
#define RIO_MSG_DEFER 0x02
#endif

static bool load_rio_functions(SOCKET s) {
    if (g_rio_loaded) return true;

    DWORD dwBytes = 0;
    g_rio.cbSize = sizeof(RIO_EXTENSION_FUNCTION_TABLE);

    int ret = WSAIoctl(
        s,
        SIO_GET_MULTIPLE_EXTENSION_FUNCTION_POINTER,
        (void*)&WSAID_MULTIPLE_RIO_VAL,
        sizeof(WSAID_MULTIPLE_RIO_VAL),
        (void*)&g_rio,
        sizeof(g_rio),
        &dwBytes,
        NULL,
        NULL
    );

    if (ret == 0 && g_rio.RIOSend && g_rio.RIOReceive && g_rio.RIOCreateCompletionQueue) {
        g_rio_loaded = true;
        return true;
    }
    return false;
}

RIO_API int jarvis_rio_is_available(void) {
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        return 0;
    }

    SOCKET s = WSASocketW(AF_INET, SOCK_DGRAM, IPPROTO_UDP, NULL, 0, WSA_FLAG_REGISTERED_IO);
    if (s == INVALID_SOCKET) {
        WSACleanup();
        return 0;
    }

    bool available = load_rio_functions(s);
    closesocket(s);
    return available ? 1 : 0;
}

RIO_API JarvisRioContext* jarvis_rio_create(const char* bind_ip, uint16_t bind_port, uint32_t buffer_size, uint32_t queue_depth) {
    WSADATA wsa;
    if (WSAStartup(MAKEWORD(2, 2), &wsa) != 0) {
        return NULL;
    }

    SOCKET s = WSASocketW(AF_INET, SOCK_DGRAM, IPPROTO_UDP, NULL, 0, WSA_FLAG_REGISTERED_IO);
    if (s == INVALID_SOCKET) {
        return NULL;
    }

    if (!load_rio_functions(s)) {
        closesocket(s);
        return NULL;
    }

    /* Socket options */
    int opt = 1;
    setsockopt(s, SOL_SOCKET, SO_REUSEADDR, (const char*)&opt, sizeof(opt));
    int buf_size_val = 16 * 1024 * 1024;
    setsockopt(s, SOL_SOCKET, SO_RCVBUF, (const char*)&buf_size_val, sizeof(buf_size_val));
    setsockopt(s, SOL_SOCKET, SO_SNDBUF, (const char*)&buf_size_val, sizeof(buf_size_val));

    /* Bind */
    struct sockaddr_in addr;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(bind_port);
    if (bind_ip && strlen(bind_ip) > 0) {
        inet_pton(AF_INET, bind_ip, &addr.sin_addr);
    } else {
        addr.sin_addr.s_addr = INADDR_ANY;
    }

    if (bind(s, (struct sockaddr*)&addr, sizeof(addr)) != 0) {
        closesocket(s);
        return NULL;
    }

    /* Allocate page-aligned memory */
    if (buffer_size < 64 * 1024) buffer_size = 64 * 1024;
    char* raw_buf = (char*)VirtualAlloc(NULL, buffer_size, MEM_COMMIT | MEM_RESERVE, PAGE_READWRITE);
    if (!raw_buf) {
        closesocket(s);
        return NULL;
    }

    /* Register buffer with RIO */
    RIO_BUFFERID buf_id = g_rio.RIORegisterBuffer(raw_buf, buffer_size);
    if (buf_id == RIO_INVALID_BUFFERID) {
        VirtualFree(raw_buf, 0, MEM_RELEASE);
        closesocket(s);
        return NULL;
    }

    /* Create completion queue and request queue */
    if (queue_depth < 64) queue_depth = 64;
    DWORD cq_size = queue_depth * 2;
    RIO_CQ cq = g_rio.RIOCreateCompletionQueue(cq_size, NULL);
    if (cq == RIO_INVALID_CQ) {
        g_rio.RIODeregisterBuffer(buf_id);
        VirtualFree(raw_buf, 0, MEM_RELEASE);
        closesocket(s);
        return NULL;
    }

    RIO_RQ rq = g_rio.RIOCreateRequestQueue(
        s,
        queue_depth, /* MaxOutstandingReceive */
        1,           /* MaxReceiveDataBuffers */
        queue_depth, /* MaxOutstandingSend */
        1,           /* MaxSendDataBuffers */
        cq,          /* ReceiveCQ */
        cq,          /* SendCQ */
        NULL         /* SocketContext */
    );

    if (rq == RIO_INVALID_RQ) {
        g_rio.RIOCloseCompletionQueue(cq);
        g_rio.RIODeregisterBuffer(buf_id);
        VirtualFree(raw_buf, 0, MEM_RELEASE);
        closesocket(s);
        return NULL;
    }

    JarvisRioContext* ctx = (JarvisRioContext*)malloc(sizeof(JarvisRioContext));
    if (!ctx) {
        g_rio.RIOCloseCompletionQueue(cq);
        g_rio.RIODeregisterBuffer(buf_id);
        VirtualFree(raw_buf, 0, MEM_RELEASE);
        closesocket(s);
        return NULL;
    }

    ctx->socket = s;
    ctx->completion_queue = cq;
    ctx->request_queue = rq;
    ctx->buffer_id = buf_id;
    ctx->buffer_base = raw_buf;
    ctx->buffer_size = buffer_size;
    ctx->slice_size = 64 * 1024;
    ctx->total_slices = buffer_size / ctx->slice_size;
    ctx->queue_depth = queue_depth;
    ctx->is_initialized = true;

    /* Phase 24 tracing */
    ctx->submits_total = 0;
    ctx->completions_total = 0;
    ctx->errors_total = 0;
    ctx->bytes_total = 0;
    ctx->send_queue_depth = 0;
    ctx->recv_queue_depth = 0;
    ctx->last_completion_lag_us = 0;

    return ctx;
}

RIO_API int jarvis_rio_connect(JarvisRioContext* ctx, const char* target_ip, uint16_t target_port) {
    if (!ctx || !ctx->is_initialized) return 0;
    struct sockaddr_in target_addr;
    memset(&target_addr, 0, sizeof(target_addr));
    target_addr.sin_family = AF_INET;
    target_addr.sin_port = htons(target_port);
    inet_pton(AF_INET, target_ip, &target_addr.sin_addr);

    if (connect(ctx->socket, (struct sockaddr*)&target_addr, sizeof(target_addr)) == 0) {
        return 1;
    }
    return 0;
}

RIO_API int jarvis_rio_send_batch(JarvisRioContext* ctx, const uint32_t* offsets, const uint32_t* lengths, uint32_t count) {
    if (!ctx || !ctx->is_initialized || count == 0) return 0;

    uint32_t submitted = 0;
    for (uint32_t i = 0; i < count; ++i) {
        RIO_BUF buf;
        buf.BufferId = ctx->buffer_id;
        buf.Offset = offsets[i];
        buf.Length = lengths[i];

        DWORD flags = (i < count - 1) ? RIO_MSG_DEFER : 0;

        BOOL res = g_rio.RIOSend(
            ctx->request_queue,
            &buf,
            1,
            flags,
            (PVOID)(uintptr_t)i
        );

        if (res) {
            submitted++;
            ctx->bytes_total += lengths[i];
        } else {
            ctx->errors_total += (count - submitted);
            break;
        }
    }
    ctx->submits_total += submitted;
    ctx->send_queue_depth += submitted;
    return (int)submitted;
}

RIO_API int jarvis_rio_post_receives(JarvisRioContext* ctx, const uint32_t* offsets, const uint32_t* lengths, uint32_t count) {
    if (!ctx || !ctx->is_initialized || count == 0) return 0;

    uint32_t posted = 0;
    for (uint32_t i = 0; i < count; ++i) {
        RIO_BUF buf;
        buf.BufferId = ctx->buffer_id;
        buf.Offset = offsets[i];
        buf.Length = lengths[i];

        DWORD flags = (i < count - 1) ? RIO_MSG_DEFER : 0;

        BOOL res = g_rio.RIOReceive(
            ctx->request_queue,
            &buf,
            1,
            flags,
            (PVOID)(uintptr_t)i
        );

        if (res) {
            posted++;
        } else {
            ctx->errors_total += (count - posted);
            break;
        }
    }
    ctx->recv_queue_depth += posted;
    return (int)posted;
}

RIO_API int jarvis_rio_dequeue_completions(JarvisRioContext* ctx, RIORESULT* results, uint32_t max_results) {
    if (!ctx || !ctx->is_initialized || !results || max_results == 0) return 0;
    ULONG num = g_rio.RIODequeueCompletion(ctx->completion_queue, results, max_results);
    if (num == RIO_CORRUPT_CQ) {
        ctx->errors_total++;
        return -1;
    }
    ctx->completions_total += num;
    if (ctx->send_queue_depth >= (uint32_t)num) {
        ctx->send_queue_depth -= (uint32_t)num;
    } else {
        ctx->send_queue_depth = 0;
    }
    return (int)num;
}

RIO_API int jarvis_rio_set_socket_buffers(JarvisRioContext* ctx, int rcvbuf, int sndbuf) {
    if (!ctx || !ctx->is_initialized || ctx->socket == INVALID_SOCKET) return 0;
    if (rcvbuf > 0) {
        setsockopt(ctx->socket, SOL_SOCKET, SO_RCVBUF, (const char*)&rcvbuf, sizeof(rcvbuf));
    }
    if (sndbuf > 0) {
        setsockopt(ctx->socket, SOL_SOCKET, SO_SNDBUF, (const char*)&sndbuf, sizeof(sndbuf));
    }
    return 1;
}

RIO_API int jarvis_rio_get_socket_rcvbuf(JarvisRioContext* ctx) {
    if (!ctx || !ctx->is_initialized || ctx->socket == INVALID_SOCKET) return 0;
    int optval = 0;
    int optlen = sizeof(optval);
    if (getsockopt(ctx->socket, SOL_SOCKET, SO_RCVBUF, (char*)&optval, &optlen) == 0) {
        return optval;
    }
    return 0;
}

RIO_API int jarvis_rio_get_stats(JarvisRioContext* ctx, uint64_t* submits, uint64_t* completions, uint64_t* errors, uint32_t* sq_depth, uint32_t* cq_depth) {
    if (!ctx || !ctx->is_initialized) return 0;
    if (submits) *submits = ctx->submits_total;
    if (completions) *completions = ctx->completions_total;
    if (errors) *errors = ctx->errors_total;
    if (sq_depth) *sq_depth = ctx->send_queue_depth;
    if (cq_depth) *cq_depth = ctx->recv_queue_depth;
    return 1;
}

RIO_API void jarvis_rio_destroy(JarvisRioContext* ctx) {
    if (!ctx) return;
    if (ctx->is_initialized) {
        if (ctx->completion_queue != RIO_INVALID_CQ) {
            g_rio.RIOCloseCompletionQueue(ctx->completion_queue);
        }
        if (ctx->buffer_id != RIO_INVALID_BUFFERID) {
            g_rio.RIODeregisterBuffer(ctx->buffer_id);
        }
        if (ctx->buffer_base) {
            VirtualFree(ctx->buffer_base, 0, MEM_RELEASE);
        }
        if (ctx->socket != INVALID_SOCKET) {
            closesocket(ctx->socket);
        }
        ctx->is_initialized = false;
    }
    free(ctx);
}

#endif /* _WIN32 */

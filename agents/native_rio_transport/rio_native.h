/*
 * JARVIS OS — Phase 23: Windows Registered I/O (RIO) Native C Extension
 * Header definitions for vectorized, zero-copy UDP I/O.
 */

#ifndef JARVIS_RIO_NATIVE_H
#define JARVIS_RIO_NATIVE_H

#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <winsock2.h>
#include <ws2tcpip.h>
#include <mswsock.h>
#include <stdint.h>
#include <stdbool.h>

#ifdef RIO_EXPORTS
#define RIO_API __declspec(dllexport)
#else
#define RIO_API __declspec(dllimport)
#endif

#pragma comment(lib, "ws2_32.lib")

#ifdef __cplusplus
extern "C" {
#endif

/* RIO Context handle */
typedef struct {
    SOCKET socket;
    RIO_CQ completion_queue;
    RIO_RQ request_queue;
    RIO_BUFFERID buffer_id;
    char* buffer_base;
    uint32_t buffer_size;
    uint32_t slice_size;
    uint32_t total_slices;
    uint32_t queue_depth;
    bool is_initialized;

    /* Phase 24 Native Tracing Counters */
    uint64_t submits_total;
    uint64_t completions_total;
    uint64_t errors_total;
    uint64_t bytes_total;
    uint32_t send_queue_depth;
    uint32_t recv_queue_depth;
    uint64_t last_completion_lag_us;
} JarvisRioContext;

/* Core Exported Functions */
RIO_API int jarvis_rio_is_available(void);
RIO_API JarvisRioContext* jarvis_rio_create(const char* bind_ip, uint16_t bind_port, uint32_t buffer_size, uint32_t queue_depth);
RIO_API int jarvis_rio_connect(JarvisRioContext* ctx, const char* target_ip, uint16_t target_port);
RIO_API int jarvis_rio_send_batch(JarvisRioContext* ctx, const uint32_t* offsets, const uint32_t* lengths, uint32_t count);
RIO_API int jarvis_rio_post_receives(JarvisRioContext* ctx, const uint32_t* offsets, const uint32_t* lengths, uint32_t count);
RIO_API int jarvis_rio_dequeue_completions(JarvisRioContext* ctx, RIORESULT* results, uint32_t max_results);
RIO_API int jarvis_rio_set_socket_buffers(JarvisRioContext* ctx, int rcvbuf, int sndbuf);
RIO_API int jarvis_rio_get_socket_rcvbuf(JarvisRioContext* ctx);
RIO_API int jarvis_rio_get_stats(JarvisRioContext* ctx, uint64_t* submits, uint64_t* completions, uint64_t* errors, uint32_t* sq_depth, uint32_t* cq_depth);
RIO_API void jarvis_rio_destroy(JarvisRioContext* ctx);

#ifdef __cplusplus
}
#endif

#else
/* Non-Windows stub */
#define RIO_API
typedef void* JarvisRioContext;
#endif

#endif /* JARVIS_RIO_NATIVE_H */

/*
 * panner_node.h - Custom equal-power panning node for miniaudio
 *
 * Implements mono-to-stereo panning with:
 * - Equal power pan law: L = cos(θ), R = sin(θ) where θ = (pan+1) * π/4
 * - Smooth interpolation when pan value changes
 */

#ifndef PANNER_NODE_H
#define PANNER_NODE_H

#include "miniaudio.h"

#ifdef __cplusplus
extern "C" {
#endif

/*
 * Portable atomic float operations.
 * miniaudio's atomic float functions are internal (static inline) and not
 * part of the public API, so we define our own using compiler intrinsics.
 *
 * Note: __atomic_* builtins don't support float directly, so we type-pun
 * through a union to use 32-bit integer atomics.
 */
#if defined(__GNUC__) || defined(__clang__)
    /* GCC/Clang: use __atomic builtins with type punning */
    #include <stdint.h>
    static inline void panner_atomic_store_f32(volatile float* dst, float src) {
        union { float f; uint32_t i; } u;
        u.f = src;
        __atomic_store_n((volatile uint32_t*)dst, u.i, __ATOMIC_RELEASE);
    }
    static inline float panner_atomic_load_f32(volatile const float* ptr) {
        union { float f; uint32_t i; } u;
        u.i = __atomic_load_n((volatile const uint32_t*)ptr, __ATOMIC_ACQUIRE);
        return u.f;
    }
#elif defined(_MSC_VER)
    /* MSVC: use Interlocked intrinsics with type punning */
    #include <intrin.h>
    static __forceinline void panner_atomic_store_f32(volatile float* dst, float src) {
        union { float f; long i; } u;
        u.f = src;
        _InterlockedExchange((volatile long*)dst, u.i);
    }
    static __forceinline float panner_atomic_load_f32(volatile const float* ptr) {
        union { float f; long i; } u;
        /* Atomic load via no-op OR */
        u.i = _InterlockedOr((volatile long*)ptr, 0);
        return u.f;
    }
#else
    #error "Unsupported compiler for atomic operations"
#endif

/* Number of samples to interpolate over when pan changes */
#define PANNER_SMOOTH_SAMPLES 256

/* Panner node structure - ma_node_base MUST be first member */
typedef struct {
    ma_node_base base;

    /* Current target pan set from main thread (atomic) */
    volatile float target_pan;

    /* Previous pan value for interpolation (audio thread only) */
    float prev_pan;

    /* Current pan being rendered (audio thread only) */
    float current_pan;

    /* Interpolation state (audio thread only) */
    ma_uint32 smooth_samples_remaining;
    float pan_increment;
} panner_node;

/* Initialize a panner node */
ma_result panner_node_init(
    ma_node_graph* pNodeGraph,
    float initial_pan,
    const ma_allocation_callbacks* pAllocationCallbacks,
    panner_node* pPanner
);

/* Uninitialize a panner node */
void panner_node_uninit(
    panner_node* pPanner,
    const ma_allocation_callbacks* pAllocationCallbacks
);

/* Set the pan value (thread-safe, can be called from any thread) */
void panner_node_set_pan(panner_node* pPanner, float pan);

/* Get the current target pan value (thread-safe) */
float panner_node_get_pan(const panner_node* pPanner);

#ifdef __cplusplus
}
#endif

#endif /* PANNER_NODE_H */

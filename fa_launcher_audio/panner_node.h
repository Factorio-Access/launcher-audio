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

/* Number of samples to interpolate over when pan changes */
#define PANNER_SMOOTH_SAMPLES 256

/* Panner node structure - ma_node_base MUST be first member */
typedef struct {
    ma_node_base base;

    /* Current target pan set from main thread (atomic) */
    MA_ATOMIC(4, float) target_pan;

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

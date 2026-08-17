/**
 * @file telemetry.h
 * @brief Multi-channel telemetry sampling API.
 */

#ifndef TELEMETRY_H
#define TELEMETRY_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

/** Maximum packed payload size of one frame, in bytes. */
#define TELEMETRY_MAX_SAMPLE_SIZE 128U
/** Number of channel registers available for configuration. */
#define TELEMETRY_MAX_CHANNELS 16U
/**
 * Reserved register index passed to telemetry_subscribe() to clear a channel.
 */
#define TELEMETRY_NULL_INDEX 0U

/** Result codes returned by the telemetry API and callbacks. */
typedef enum {
    /** The operation completed successfully. */
    TELEMETRY_OK = 0,
    /** An argument was NULL or outside the supported range. */
    TELEMETRY_INVALID_ARGUMENT = -1,
    /** The channel list or queue cannot accept more data. */
    TELEMETRY_FULL = -3,
    /** Sampling was requested before telemetry_start(). */
    TELEMETRY_NOT_CONFIGURED = -5,
    /** No frame is currently queued. */
    TELEMETRY_EMPTY = -6
} telemetry_status_t;

/** One channel register; an unassigned register has a NULL data pointer. */
typedef struct {
    /** Register index configured for this channel. */
    uint16_t index;
    /** Raw value size in bytes. */
    uint16_t value_size;
    /** Pointer to the mapped raw value. */
    const uint8_t *data;
} telemetry_channel_t;

/** State returned by a platform critical-section entry callback. */
typedef uintptr_t telemetry_critical_state_t;

/** Enters the critical section used to protect queue state. */
typedef telemetry_critical_state_t (*telemetry_critical_enter_t)(void *context);

/** Leaves the critical section and restores the platform state. */
typedef void (*telemetry_critical_exit_t)(
    void *context,
    telemetry_critical_state_t state);

/** Platform-provided synchronization hooks for queue access. */
typedef struct {
    /** Enters the critical section, or NULL for no synchronization. */
    telemetry_critical_enter_t enter;
    /** Leaves the critical section, or NULL for no synchronization. */
    telemetry_critical_exit_t exit;
    /** Platform-specific context passed to both callbacks. */
    void *context;
} telemetry_sync_t;

/** Runtime state for one statically allocated telemetry acquisition. */
typedef struct {
    /** Channel registers, addressed directly by slot number. */
    telemetry_channel_t channels[TELEMETRY_MAX_CHANNELS];
    /** Base position/velocity loop frequency in hertz. */
    uint32_t base_frequency_hz;
    /** Monitoring divider applied to the base loop. */
    uint32_t prescaler;
    /** User-configured divider used as the adaptive-rate lower bound. */
    uint32_t configured_prescaler;
    /** Base-loop tick at which the next frame becomes due. */
    uint64_t next_due_tick;
    /** Caller-owned circular storage containing timestamped frames. */
    uint8_t *queue_storage;
    /** Size of queue_storage, in bytes. */
    size_t queue_storage_size;
    /** Number of frame positions available in queue_storage. */
    size_t queue_capacity;
    /** Index of the oldest queued frame. */
    size_t queue_head;
    /** Number of queued frames. */
    size_t queue_count;
    /** Packed raw payload size of one frame. */
    size_t sample_size;
    /** Whether sampling has been started. */
    bool running;
    /** Whether queue occupancy controls the effective sampling divider. */
    bool adaptive_rate;
    /** Fixed-point EMA of queue occupancy, with eight fractional bits. */
    uint32_t adaptive_occupancy_q8;
    /** Base-loop tick at which adaptive control is next evaluated. */
    uint64_t adaptive_next_update_tick;
    /** Platform synchronization hooks for concurrent queue access. */
    telemetry_sync_t sync;
} telemetry_t;

/**
 * @brief Initializes caller-owned telemetry state and queue storage.
 *
 * No memory is allocated. The queue storage must remain valid for the
 * lifetime of the telemetry instance.
 *
 * The synchronization hooks protect short queue operations when sampling and
 * networking can run concurrently, for example when sampling runs from an
 * ISR. They must not block and must be safe to use from the sampling
 * context. Passing NULL disables synchronization and is valid when the caller
 * guarantees that queue access is not concurrent.
 *
 * @param[out] telemetry Caller-owned telemetry state.
 * @param[in] queue_storage Caller-owned byte storage for queued frames.
 * @param[in] queue_storage_size Size of queue_storage, in bytes.
 * @param[in] sync Synchronization hooks, or NULL to disable synchronization.
 * @return TELEMETRY_OK, or TELEMETRY_INVALID_ARGUMENT for invalid arguments,
 *         including mismatched synchronization hooks.
 */
telemetry_status_t telemetry_init(
    telemetry_t *telemetry,
    uint8_t *queue_storage,
    size_t queue_storage_size,
    const telemetry_sync_t *sync);

/** Configures the sampling divider while telemetry is stopped. */
telemetry_status_t telemetry_set_prescaler(
    telemetry_t *telemetry,
    uint32_t prescaler);

/** Enables or disables queue-occupancy-based sampling-rate adaptation while stopped. */
telemetry_status_t telemetry_set_adaptive_rate(
    telemetry_t *telemetry,
    bool enabled);

/** Returns whether telemetry sampling is currently running. */
bool telemetry_is_running(const telemetry_t *telemetry);

/** Returns the configured sampling divider, or zero for a NULL instance. */
uint32_t telemetry_get_prescaler(const telemetry_t *telemetry);

/** Returns whether queue-occupancy-based sampling-rate adaptation is enabled. */
bool telemetry_get_adaptive_rate(const telemetry_t *telemetry);

/**
 * @brief Assigns or clears one mapped register in the common monitoring frame.
 *
 * Each of the TELEMETRY_MAX_CHANNELS channel registers is addressed directly
 * by its slot number and holds one caller-supplied data pointer. Passing
 * TELEMETRY_NULL_INDEX with NULL data and zero value size clears the channel;
 * any other valid value replaces whatever was previously configured there.
 * The packed sample payload concatenates the values of all assigned
 * registers in ascending slot order, skipping unassigned ones. Because a
 * register's position depends only on the current configuration and not on
 * the history of prior assignments, the networking master can always
 * recompute the payload layout from the current register configuration.
 *
 * @param[in,out] telemetry Telemetry instance that is not running.
 * @param[in] channel Channel register slot, in [0, TELEMETRY_MAX_CHANNELS).
 * @param[in] register_index Register index to assign, or
 *            TELEMETRY_NULL_INDEX to clear the channel.
 * @return TELEMETRY_OK, or an error if channel is out of range, the
 *         the configured payload would exceed TELEMETRY_MAX_SAMPLE_SIZE.
 */
telemetry_status_t telemetry_subscribe(
    telemetry_t *telemetry,
    uint16_t channel,
    uint16_t register_index,
    const uint8_t *data,
    uint16_t value_size);

/**
 * @brief Configures the prescaled sampler and starts sampling.
 *
 * Every subscribed channel is sampled every prescaler base-loop ticks and contributes to one
 * packed frame with one shared timestamp. The supplied static queue storage
 * determines the number of positions. Sampling reports TELEMETRY_FULL when
 * the queue cannot accept another frame.
 *
 * @param[in,out] telemetry Configured telemetry instance.
 * @param[in] base_frequency_hz Position/velocity loop frequency in hertz.
 * @param[in] prescaler Monitoring frequency divider; must be non-zero.
 * @param[in] now_tick Current monotonic base-loop tick.
 * @return TELEMETRY_OK, or an error if the configuration is invalid or the
 *         supplied queue storage cannot hold one frame.
 */
telemetry_status_t telemetry_start(
    telemetry_t *telemetry,
    uint32_t base_frequency_hz,
    uint32_t prescaler,
    uint64_t now_tick);

/**
 * @brief Stops sampling and clears the queued-frame state.
 *
 * @param[in,out] telemetry Telemetry instance to stop. NULL is allowed.
 * The caller-owned storage remains available for a later telemetry_start().
 */
void telemetry_stop(telemetry_t *telemetry);

/**
 * @brief Samples all configured channels when the prescaler has elapsed.
 *
 * A failed channel callback discards the complete frame, keeping channels
 * aligned on the shared timestamp.
 *
 * @param[in,out] telemetry Running telemetry instance.
 * @param[in] now_tick Current monotonic base-loop tick.
 * @return 1 when a frame was queued, 0 when no frame was due or a channel
 *         callback failed, TELEMETRY_FULL when the queue is full, or another
 *         negative telemetry_status_t error.
 */
int32_t telemetry_process(telemetry_t *telemetry, uint64_t now_tick);

/**
 * @brief Copies the oldest queued frame into caller-owned storage and removes it.
 *
 * The frame is claimed and removed from the queue while holding the
 * critical section, before this function returns, keeping the critical
 * section short and letting an ISR producer keep queuing new frames while
 * the caller processes the copied frame. Call this in a loop, for example
 * guided by telemetry_pending_count(), to drain every queued frame; data may
 * be a buffer local to the caller.
 *
 * @param[in,out] telemetry Running telemetry instance.
 * @param[out] timestamp_tick Shared base-loop tick for the frame.
 * @param[out] data Caller-owned buffer that receives the packed channel
 *             values, in ascending channel-register slot order.
 * @param[in] data_capacity Capacity of data, in bytes.
 * @param[out] data_size Number of bytes written to data.
 * @return TELEMETRY_OK when a frame was copied, TELEMETRY_EMPTY when no
 *         frame is queued, TELEMETRY_FULL when data_capacity is smaller than
 *         one frame, or TELEMETRY_INVALID_ARGUMENT for invalid arguments.
 */
telemetry_status_t telemetry_read_frame(
    telemetry_t *telemetry,
    uint64_t *timestamp_tick,
    uint8_t *data,
    size_t data_capacity,
    uint16_t *data_size);

/**
 * @brief Copies as many queued frames as fit into caller-owned storage.
 *
 * The output starts with a little-endian uint16_t frame count, followed by
 * each frame serialized as its timestamp and packed channel payload. Frames
 * are copied oldest first and removed from the queue.
 *
 * @param[in,out] telemetry Running telemetry instance.
 * @param[out] data Destination buffer for serialized frames.
 * @param[in] data_capacity Capacity of data, in bytes.
 * @param[out] data_size Number of bytes written to data, including the frame
 *             count when at least one frame was copied.
 * @return TELEMETRY_OK when at least one frame was copied,
 *         TELEMETRY_EMPTY when no frame is queued, TELEMETRY_FULL when the
 *         buffer cannot hold one complete frame, or
 *         TELEMETRY_INVALID_ARGUMENT for invalid arguments.
 */
telemetry_status_t telemetry_read_frames(
    telemetry_t *telemetry,
    uint8_t *data,
    size_t data_capacity,
    uint16_t *data_size);

/**
 * @brief Returns the number of queued frames.
 *
 * @param[in] telemetry Telemetry instance; NULL returns zero.
 * @return Number of queued frames.
 */
size_t telemetry_pending_count(const telemetry_t *telemetry);

/**
 * @brief Returns the packed raw payload size of one frame.
 *
 * @param[in] telemetry Telemetry instance; NULL returns zero.
 * @return Payload size in bytes, excluding the shared timestamp.
 */
size_t telemetry_sample_size(const telemetry_t *telemetry);

#ifdef __cplusplus
}
#endif

#endif /* TELEMETRY_H */

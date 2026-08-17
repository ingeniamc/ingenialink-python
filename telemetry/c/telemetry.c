#include "telemetry.h"

#include <stdbool.h>
#include <string.h>

#define TELEMETRY_ADAPTIVE_OCCUPANCY_SHIFT 8U
#define TELEMETRY_ADAPTIVE_EMA_SHIFT 4U
#define TELEMETRY_ADAPTIVE_LOWER_TARGET_NUMERATOR 1U
#define TELEMETRY_ADAPTIVE_LOWER_TARGET_DENOMINATOR 4U
#define TELEMETRY_ADAPTIVE_UPPER_TARGET_NUMERATOR 7U
#define TELEMETRY_ADAPTIVE_UPPER_TARGET_DENOMINATOR 10U
#define TELEMETRY_ADAPTIVE_UPDATE_PERIOD_US 100U
#define TELEMETRY_ADAPTIVE_MAX_DIVIDER_MULTIPLIER 8U
#define TELEMETRY_ADAPTIVE_STEP_DIVISOR 64U

/** Returns the beginning of one circular queue frame. */
static uint8_t *telemetry_queue_position(
    const telemetry_t *telemetry,
    size_t position)
{
    return &telemetry->queue_storage[position * (sizeof(uint64_t) + telemetry->sample_size)];
}

/** Enters the configured platform critical section, if one exists. */
static telemetry_critical_state_t telemetry_enter_critical(const telemetry_t *telemetry)
{
    telemetry_critical_state_t result = 0U;

    if (telemetry->sync.enter != NULL)
    {
        result = telemetry->sync.enter(telemetry->sync.context);
    }

    return result;
}

/** Leaves the configured platform critical section, if one exists. */
static void telemetry_exit_critical(
    const telemetry_t *telemetry,
    telemetry_critical_state_t state)
{
    if (telemetry->sync.exit != NULL)
    {
        telemetry->sync.exit(telemetry->sync.context, state);
    }
}

/** Returns the adaptive controller period for the configured base frequency. */
static uint64_t telemetry_adaptive_update_interval_ticks(
    const telemetry_t *telemetry)
{
    uint64_t interval_ticks =
        ((uint64_t)telemetry->base_frequency_hz * TELEMETRY_ADAPTIVE_UPDATE_PERIOD_US
         + 999999U)
        / 1000000U;

    return interval_ticks == 0U ? 1U : interval_ticks;
}

/** Adjusts the effective divider from a smoothed queue-occupancy estimate. */
static void telemetry_update_adaptive_rate(
    telemetry_t *telemetry,
    uint64_t now_tick)
{
    uint32_t occupancy_q8;
    uint32_t lower_target_q8;
    uint32_t upper_target_q8;
    uint32_t next_prescaler;
    uint32_t step;
    uint32_t occupancy_delta;
    uint32_t ema_step;
    uint64_t desired_prescaler;
    uint64_t occupancy_q8_wide;
    uint64_t max_prescaler;

    if (!telemetry->adaptive_rate
        || (telemetry->queue_capacity == 0U)
        || (now_tick < telemetry->adaptive_next_update_tick))
    {
        return;
    }

    occupancy_q8_wide = (uint64_t)telemetry->queue_count
        << TELEMETRY_ADAPTIVE_OCCUPANCY_SHIFT;
    occupancy_q8 = occupancy_q8_wide > UINT32_MAX
        ? UINT32_MAX
        : (uint32_t)occupancy_q8_wide;
    if (occupancy_q8 > telemetry->adaptive_occupancy_q8)
    {
        occupancy_delta = occupancy_q8 - telemetry->adaptive_occupancy_q8;
        ema_step = (occupancy_delta >> TELEMETRY_ADAPTIVE_EMA_SHIFT)
            + ((occupancy_delta & ((1U << TELEMETRY_ADAPTIVE_EMA_SHIFT) - 1U)) != 0U);
        if (ema_step == 0U)
        {
            ema_step = 1U;
        }
        telemetry->adaptive_occupancy_q8 += ema_step;
    }
    else if (occupancy_q8 < telemetry->adaptive_occupancy_q8)
    {
        occupancy_delta = telemetry->adaptive_occupancy_q8 - occupancy_q8;
        ema_step = (occupancy_delta >> TELEMETRY_ADAPTIVE_EMA_SHIFT)
            + ((occupancy_delta & ((1U << TELEMETRY_ADAPTIVE_EMA_SHIFT) - 1U)) != 0U);
        if (ema_step == 0U)
        {
            ema_step = 1U;
        }
        telemetry->adaptive_occupancy_q8 -= ema_step;
    }

    lower_target_q8 = (uint32_t)(((uint64_t)telemetry->queue_capacity
                                  * TELEMETRY_ADAPTIVE_LOWER_TARGET_NUMERATOR
                                  * (1U << TELEMETRY_ADAPTIVE_OCCUPANCY_SHIFT))
                                 / TELEMETRY_ADAPTIVE_LOWER_TARGET_DENOMINATOR);
    upper_target_q8 = (uint32_t)(((uint64_t)telemetry->queue_capacity
                                  * TELEMETRY_ADAPTIVE_UPPER_TARGET_NUMERATOR
                                  * (1U << TELEMETRY_ADAPTIVE_OCCUPANCY_SHIFT))
                                 / TELEMETRY_ADAPTIVE_UPPER_TARGET_DENOMINATOR);
    if (lower_target_q8 == 0U)
    {
        lower_target_q8 = 1U;
    }
    if (upper_target_q8 == 0U)
    {
        upper_target_q8 = 1U;
    }

    desired_prescaler = telemetry->prescaler;
    if (telemetry->adaptive_occupancy_q8 > upper_target_q8)
    {
        desired_prescaler = telemetry->configured_prescaler;
        desired_prescaler += (((uint64_t)telemetry->configured_prescaler
                       * (telemetry->adaptive_occupancy_q8 - upper_target_q8))
                      + upper_target_q8 - 1U)
                     / upper_target_q8;
        max_prescaler = (uint64_t)telemetry->configured_prescaler
            * TELEMETRY_ADAPTIVE_MAX_DIVIDER_MULTIPLIER;
        if (max_prescaler > UINT32_MAX)
        {
            max_prescaler = UINT32_MAX;
        }
        if (desired_prescaler > max_prescaler)
        {
            desired_prescaler = max_prescaler;
        }
        /* Do not speed back up while the smoothed queue is still above target. */
        if (desired_prescaler < telemetry->prescaler)
        {
            desired_prescaler = telemetry->prescaler;
        }
    }
    else if (telemetry->adaptive_occupancy_q8 < lower_target_q8)
    {
        desired_prescaler = telemetry->configured_prescaler;
    }

    next_prescaler = telemetry->prescaler;
    step = telemetry->configured_prescaler / TELEMETRY_ADAPTIVE_STEP_DIVISOR;
    if (step == 0U)
    {
        step = 1U;
    }
    if (next_prescaler < desired_prescaler)
    {
        next_prescaler += step;
        if (next_prescaler > desired_prescaler)
        {
            next_prescaler = (uint32_t)desired_prescaler;
        }
    }
    else if (next_prescaler > desired_prescaler)
    {
        uint32_t delta = next_prescaler - (uint32_t)desired_prescaler;
        next_prescaler -= delta > step ? step : delta;
    }

    if (next_prescaler != telemetry->prescaler)
    {
        telemetry->prescaler = next_prescaler;
        telemetry->next_due_tick = now_tick + next_prescaler;
    }
    telemetry->adaptive_next_update_tick = now_tick
        + telemetry_adaptive_update_interval_ticks(telemetry);
}

/** Appends a frame when the queue has capacity. */
static bool telemetry_queue_push(
    telemetry_t *telemetry,
    uint64_t timestamp_tick,
    const uint8_t *data)
{
    size_t write_index;
    uint8_t *position;

    if (telemetry->queue_count == telemetry->queue_capacity)
    {
        return false;
    }
    write_index = (telemetry->queue_head + telemetry->queue_count) % telemetry->queue_capacity;
    telemetry->queue_count++;

    position = telemetry_queue_position(telemetry, write_index);
    memcpy(position, &timestamp_tick, sizeof(timestamp_tick));
    memcpy(&position[sizeof(timestamp_tick)], data, telemetry->sample_size);
    return true;
}

telemetry_status_t telemetry_init(
    telemetry_t *telemetry,
    uint8_t *queue_storage,
    size_t queue_storage_size,
    const telemetry_sync_t *sync)
{
    telemetry_status_t result = TELEMETRY_OK;

    if ((telemetry == NULL)
        || ((queue_storage_size > 0U) && (queue_storage == NULL))
        || ((sync != NULL) && ((sync->enter == NULL) != (sync->exit == NULL))))
    {
        result = TELEMETRY_INVALID_ARGUMENT;
    }
    else
    {
        memset(telemetry, 0, sizeof(*telemetry));
        telemetry->queue_storage = queue_storage;
        telemetry->queue_storage_size = queue_storage_size;
        telemetry->prescaler = 1U;
        telemetry->configured_prescaler = 1U;
        if (sync != NULL)
        {
            telemetry->sync = *sync;
        }
    }

    return result;
}

telemetry_status_t telemetry_set_prescaler(telemetry_t *telemetry, uint32_t prescaler)
{
    if ((telemetry == NULL) || telemetry->running || (prescaler == 0U))
    {
        return TELEMETRY_INVALID_ARGUMENT;
    }

    telemetry->prescaler = prescaler;
    telemetry->configured_prescaler = prescaler;
    return TELEMETRY_OK;
}

telemetry_status_t telemetry_set_adaptive_rate(
    telemetry_t *telemetry,
    bool enabled)
{
    if ((telemetry == NULL) || telemetry->running)
    {
        return TELEMETRY_INVALID_ARGUMENT;
    }

    telemetry->adaptive_rate = enabled;
    return TELEMETRY_OK;
}

bool telemetry_is_running(const telemetry_t *telemetry)
{
    return (telemetry != NULL) && telemetry->running;
}

uint32_t telemetry_get_prescaler(const telemetry_t *telemetry)
{
    return telemetry == NULL ? 0U : telemetry->prescaler;
}

bool telemetry_get_adaptive_rate(const telemetry_t *telemetry)
{
    return (telemetry != NULL) && telemetry->adaptive_rate;
}

telemetry_status_t telemetry_subscribe(
    telemetry_t *telemetry,
    uint16_t channel,
    uint16_t register_index,
    const uint8_t *data,
    uint16_t value_size)
{
    telemetry_status_t result = TELEMETRY_OK;

    if ((telemetry == NULL) || telemetry->running || (channel >= TELEMETRY_MAX_CHANNELS)
        || (value_size > TELEMETRY_MAX_SAMPLE_SIZE))
    {
        result = TELEMETRY_INVALID_ARGUMENT;
    }
    else
    {
        telemetry_channel_t *slot = &telemetry->channels[channel];
        size_t previous_size = slot->data != NULL
            ? slot->value_size : 0U;

        if ((register_index == TELEMETRY_NULL_INDEX) && (data == NULL) && (value_size == 0U))
        {
            telemetry->sample_size -= previous_size;
            memset(slot, 0, sizeof(*slot));
        }
        else if ((data == NULL) || (value_size == 0U))
        {
            result = TELEMETRY_INVALID_ARGUMENT;
        }
        else if ((telemetry->sample_size - previous_size + value_size)
                 > TELEMETRY_MAX_SAMPLE_SIZE)
        {
            result = TELEMETRY_FULL;
        }
        else
        {
            telemetry->sample_size = telemetry->sample_size - previous_size + value_size;
            slot->index = register_index;
            slot->value_size = value_size;
            slot->data = data;
        }
    }

    return result;
}


telemetry_status_t telemetry_start(
    telemetry_t *telemetry,
    uint32_t base_frequency_hz,
    uint32_t prescaler,
    uint64_t now_tick)
{
    size_t position_size;
    telemetry_status_t result = TELEMETRY_OK;

    if ((telemetry == NULL) || (base_frequency_hz == 0U) || (prescaler == 0U)
        || (telemetry->sample_size == 0U) || telemetry->running)
    {
        result = TELEMETRY_INVALID_ARGUMENT;
    }
    else
    {
        position_size = sizeof(uint64_t) + telemetry->sample_size;
        telemetry->queue_capacity = telemetry->queue_storage_size / position_size;
        if (telemetry->queue_capacity == 0U)
        {
            result = TELEMETRY_FULL;
        }
        else
        {
            telemetry->base_frequency_hz = base_frequency_hz;
            telemetry->prescaler = prescaler;
            telemetry->configured_prescaler = prescaler;
            telemetry->next_due_tick = now_tick + prescaler;
            telemetry->queue_head = 0U;
            telemetry->queue_count = 0U;
            telemetry->adaptive_occupancy_q8 = 0U;
            telemetry->adaptive_next_update_tick = now_tick;
            telemetry->running = true;
        }
    }

    return result;
}

void telemetry_stop(telemetry_t *telemetry)
{
    if (telemetry != NULL)
    {
        telemetry_critical_state_t critical_state = telemetry_enter_critical(telemetry);

        telemetry->queue_capacity = 0U;
        telemetry->queue_head = 0U;
        telemetry->queue_count = 0U;
        telemetry->running = false;
        telemetry_exit_critical(telemetry, critical_state);
    }
}

int32_t telemetry_process(telemetry_t *telemetry, uint64_t now_tick)
{
    uint8_t sample_data[TELEMETRY_MAX_SAMPLE_SIZE];
    size_t channel_index;
    size_t data_offset = 0U;
    telemetry_critical_state_t critical_state;
    int32_t result = TELEMETRY_NOT_CONFIGURED;
    bool sampling_due = false;
    bool running = false;

    if (telemetry == NULL)
    {
        result = TELEMETRY_NOT_CONFIGURED;
    }
    else
    {
        critical_state = telemetry_enter_critical(telemetry);
        running = telemetry->running;
        if (running)
        {
            telemetry_update_adaptive_rate(telemetry, now_tick);
            sampling_due = now_tick >= telemetry->next_due_tick;
        }
        telemetry_exit_critical(telemetry, critical_state);

        if (!sampling_due)
        {
            result = running ? 0 : TELEMETRY_NOT_CONFIGURED;
        }
        else
        {
            for (channel_index = 0U;
                 channel_index < TELEMETRY_MAX_CHANNELS;
                 channel_index++)
            {
                telemetry_channel_t *channel = &telemetry->channels[channel_index];

                if (channel->data != NULL)
                {
                    memcpy(&sample_data[data_offset], channel->data, channel->value_size);
                    data_offset += channel->value_size;
                }
            }

            critical_state = telemetry_enter_critical(telemetry);
            if (telemetry->running)
            {
                telemetry->next_due_tick = now_tick + telemetry->prescaler;
                result = telemetry_queue_push(telemetry, now_tick, sample_data)
                    ? 1
                    : TELEMETRY_FULL;
            }
            telemetry_exit_critical(telemetry, critical_state);
        }
    }

    return result;
}

telemetry_status_t telemetry_read_frame(
    telemetry_t *telemetry,
    uint64_t *timestamp_tick,
    uint8_t *data,
    size_t data_capacity,
    uint16_t *data_size)
{
    telemetry_status_t result;

    if ((telemetry == NULL) || (timestamp_tick == NULL) || (data_size == NULL)
        || ((data_capacity > 0U) && (data == NULL)))
    {
        result = TELEMETRY_INVALID_ARGUMENT;
    }
    else
    {
        telemetry_critical_state_t critical_state = telemetry_enter_critical(telemetry);

        if (!telemetry->running)
        {
            result = TELEMETRY_INVALID_ARGUMENT;
        }
        else if (telemetry->queue_count == 0U)
        {
            result = TELEMETRY_EMPTY;
        }
        else if (data_capacity < telemetry->sample_size)
        {
            result = TELEMETRY_FULL;
        }
        else
        {
            const uint8_t *position = telemetry_queue_position(telemetry, telemetry->queue_head);

            memcpy(timestamp_tick, position, sizeof(*timestamp_tick));
            memcpy(data, &position[sizeof(*timestamp_tick)], telemetry->sample_size);
            *data_size = (uint16_t)telemetry->sample_size;
            telemetry->queue_head = (telemetry->queue_head + 1U) % telemetry->queue_capacity;
            telemetry->queue_count--;
            result = TELEMETRY_OK;
        }

        telemetry_exit_critical(telemetry, critical_state);
    }

    return result;
}

telemetry_status_t telemetry_read_frames(
    telemetry_t *telemetry,
    uint8_t *data,
    size_t data_capacity,
    uint16_t *data_size)
{
    telemetry_status_t result;

    if ((telemetry == NULL) || (data_size == NULL)
        || ((data_capacity > 0U) && (data == NULL)))
    {
        result = TELEMETRY_INVALID_ARGUMENT;
    }
    else
    {
        size_t frame_size = sizeof(uint64_t) + telemetry->sample_size;
        size_t max_frames;
        size_t frame_count;
        size_t first_frame_count;
        size_t second_frame_count;
        size_t first_bytes;
        telemetry_critical_state_t critical_state;

        *data_size = 0U;
        result = TELEMETRY_EMPTY;
        if (data_capacity < sizeof(uint16_t) + frame_size)
        {
            result = TELEMETRY_FULL;
        }
        else
        {
            max_frames = (data_capacity - sizeof(uint16_t)) / frame_size;
            if (max_frames > (0xFFFFU - sizeof(uint16_t)) / frame_size)
            {
                max_frames = (0xFFFFU - sizeof(uint16_t)) / frame_size;
            }

            critical_state = telemetry_enter_critical(telemetry);
            if (!telemetry->running)
            {
                result = TELEMETRY_INVALID_ARGUMENT;
            }
            else if (telemetry->queue_count == 0U)
            {
                result = TELEMETRY_EMPTY;
            }
            else
            {
                frame_count = telemetry->queue_count < max_frames
                    ? telemetry->queue_count : max_frames;
                first_frame_count = telemetry->queue_capacity - telemetry->queue_head;
                if (first_frame_count > frame_count)
                {
                    first_frame_count = frame_count;
                }
                second_frame_count = frame_count - first_frame_count;
                first_bytes = first_frame_count * frame_size;

                memcpy(&data[sizeof(uint16_t)],
                       telemetry_queue_position(telemetry, telemetry->queue_head),
                       first_bytes);
                if (second_frame_count > 0U)
                {
                    memcpy(&data[sizeof(uint16_t) + first_bytes],
                           telemetry->queue_storage,
                           second_frame_count * frame_size);
                }
                telemetry->queue_head = (telemetry->queue_head + frame_count)
                    % telemetry->queue_capacity;
                telemetry->queue_count -= frame_count;
                *data_size = (uint16_t)(sizeof(uint16_t) + frame_count * frame_size);
                memcpy(data, &frame_count, sizeof(uint16_t));
                result = TELEMETRY_OK;
            }
            telemetry_exit_critical(telemetry, critical_state);
        }
    }

    return result;
}

size_t telemetry_pending_count(const telemetry_t *telemetry)
{
    size_t result = 0U;

    if (telemetry != NULL)
    {
        telemetry_critical_state_t critical_state = telemetry_enter_critical(telemetry);

        result = telemetry->queue_count;
        telemetry_exit_critical(telemetry, critical_state);
    }

    return result;
}

size_t telemetry_sample_size(const telemetry_t *telemetry)
{
    size_t result = 0U;

    if (telemetry != NULL)
    {
        telemetry_critical_state_t critical_state = telemetry_enter_critical(telemetry);

        result = telemetry->sample_size;
        telemetry_exit_critical(telemetry, critical_state);
    }

    return result;
}

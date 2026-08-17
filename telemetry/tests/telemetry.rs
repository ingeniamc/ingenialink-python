//! End-to-end tests for the direct-data C telemetry library.

use std::ffi::c_void;

const TELEMETRY_OK: i32 = 0;
const TELEMETRY_INVALID_ARGUMENT: i32 = -1;
const TELEMETRY_FULL: i32 = -3;
const TELEMETRY_NOT_CONFIGURED: i32 = -5;
const TELEMETRY_EMPTY: i32 = -6;
const TELEMETRY_MAX_CHANNELS: usize = 16;
const TELEMETRY_MAX_SAMPLE_SIZE: usize = 128;
const TELEMETRY_NULL_INDEX: u16 = 0;

#[repr(C)]
struct Channel {
    index: u16,
    value_size: u16,
    data: *const u8,
}

#[repr(C)]
struct TelemetrySync {
    enter: Option<unsafe extern "C" fn(*mut c_void) -> usize>,
    exit: Option<unsafe extern "C" fn(*mut c_void, usize)>,
    context: *mut c_void,
}

#[repr(C)]
struct Telemetry {
    channels: [Channel; TELEMETRY_MAX_CHANNELS],
    base_frequency_hz: u32,
    prescaler: u32,
    configured_prescaler: u32,
    next_due_tick: u64,
    queue_storage: *mut u8,
    queue_storage_size: usize,
    queue_capacity: usize,
    queue_head: usize,
    queue_count: usize,
    sample_size: usize,
    running: bool,
    adaptive_rate: bool,
    adaptive_occupancy_q8: u32,
    adaptive_next_update_tick: u64,
    sync: TelemetrySync,
}

#[link(name = "telemetry", kind = "static")]
unsafe extern "C" {
    fn telemetry_init(
        telemetry: *mut Telemetry,
        queue_storage: *mut u8,
        queue_storage_size: usize,
        sync: *const TelemetrySync,
    ) -> i32;
    fn telemetry_subscribe(
        telemetry: *mut Telemetry,
        channel: u16,
        register_index: u16,
        data: *const u8,
        value_size: u16,
    ) -> i32;
    fn telemetry_start(
        telemetry: *mut Telemetry,
        base_frequency_hz: u32,
        prescaler: u32,
        now_tick: u64,
    ) -> i32;
    fn telemetry_set_adaptive_rate(telemetry: *mut Telemetry, enabled: bool) -> i32;
    fn telemetry_get_prescaler(telemetry: *const Telemetry) -> u32;
    fn telemetry_process(telemetry: *mut Telemetry, now_tick: u64) -> i32;
    fn telemetry_read_frame(
        telemetry: *mut Telemetry,
        timestamp_tick: *mut u64,
        data: *mut u8,
        data_capacity: usize,
        data_size: *mut u16,
    ) -> i32;
    fn telemetry_pending_count(telemetry: *const Telemetry) -> usize;
    fn telemetry_sample_size(telemetry: *const Telemetry) -> usize;
}

fn new_telemetry(queue_storage: &mut [u8]) -> Telemetry {
    let mut telemetry: Telemetry = unsafe { std::mem::zeroed() };
    let status = unsafe {
        telemetry_init(
            &mut telemetry,
            queue_storage.as_mut_ptr(),
            queue_storage.len(),
            std::ptr::null(),
        )
    };
    assert_eq!(status, TELEMETRY_OK);
    telemetry
}

fn subscribe(telemetry: &mut Telemetry, channel: u16, index: u16, data: &[u8]) -> i32 {
    unsafe { telemetry_subscribe(telemetry, channel, index, data.as_ptr(), data.len() as u16) }
}

fn read_frame(telemetry: &mut Telemetry) -> (u64, Vec<u8>) {
    let mut timestamp = 0_u64;
    let mut data = [0_u8; TELEMETRY_MAX_SAMPLE_SIZE];
    let mut data_size = 0_u16;
    let status = unsafe {
        telemetry_read_frame(
            telemetry,
            &mut timestamp,
            data.as_mut_ptr(),
            data.len(),
            &mut data_size,
        )
    };
    assert_eq!(status, TELEMETRY_OK);
    (timestamp, data[..data_size as usize].to_vec())
}

#[test]
fn direct_data_is_sampled_into_one_frame() {
    let mut queue = [0_u8; 96];
    let mut telemetry = new_telemetry(&mut queue);
    let value = [1_u8, 2, 3, 4];

    assert_eq!(subscribe(&mut telemetry, 0, 0x1000, &value), TELEMETRY_OK);
    assert_eq!(unsafe { telemetry_sample_size(&telemetry) }, value.len());
    assert_eq!(
        unsafe { telemetry_start(&mut telemetry, 1_000, 1, 10) },
        TELEMETRY_OK
    );
    assert_eq!(unsafe { telemetry_process(&mut telemetry, 11) }, 1);
    assert_eq!(read_frame(&mut telemetry), (11, value.to_vec()));
}

#[test]
fn adaptive_rate_increases_prescaler_when_queue_is_full() {
    let mut queue = [0_u8; 24];
    let mut telemetry = new_telemetry(&mut queue);
    let value = [1_u8, 2, 3, 4];

    assert_eq!(subscribe(&mut telemetry, 0, 1, &value), TELEMETRY_OK);
    assert_eq!(
        unsafe { telemetry_set_adaptive_rate(&mut telemetry, true) },
        TELEMETRY_OK
    );
    assert_eq!(
        unsafe { telemetry_start(&mut telemetry, 1_000, 10, 0) },
        TELEMETRY_OK
    );
    assert_eq!(unsafe { telemetry_process(&mut telemetry, 10) }, 1);
    assert_eq!(unsafe { telemetry_process(&mut telemetry, 20) }, 1);
    assert_eq!(unsafe { telemetry_pending_count(&telemetry) }, 2);

    for tick in 21..=2_000 {
        unsafe { telemetry_process(&mut telemetry, tick) };
    }

    assert!(unsafe { telemetry_get_prescaler(&telemetry) } > 10);
}

#[test]
fn adaptive_rate_stabilizes_for_bursty_consumer() {
    const QUEUE_CAPACITY: usize = 100;
    const FRAME_STORAGE_SIZE: usize = 8 + TELEMETRY_MAX_SAMPLE_SIZE;
    let mut queue = [0_u8; QUEUE_CAPACITY * FRAME_STORAGE_SIZE];
    let mut telemetry = new_telemetry(&mut queue);
    let value = [7_u8; TELEMETRY_MAX_SAMPLE_SIZE];
    let mut minimum_prescaler = u32::MAX;
    let mut maximum_prescaler = 0_u32;
    let mut maximum_pending = 0_usize;

    assert_eq!(subscribe(&mut telemetry, 0, 1, &value), TELEMETRY_OK);
    assert_eq!(
        unsafe { telemetry_set_adaptive_rate(&mut telemetry, true) },
        TELEMETRY_OK
    );
    assert_eq!(
        unsafe { telemetry_start(&mut telemetry, 1_000_000, 100, 0) },
        TELEMETRY_OK
    );

    for tick in 1..=400_000 {
        unsafe { telemetry_process(&mut telemetry, tick) };

        if tick % 10_000 == 0 {
            for _ in 0..75 {
                if unsafe { telemetry_pending_count(&telemetry) } == 0 {
                    break;
                }
                read_frame(&mut telemetry);
            }
        }

        if tick >= 200_000 && tick % 1_000 == 0 {
            let prescaler = unsafe { telemetry_get_prescaler(&telemetry) };
            minimum_prescaler = minimum_prescaler.min(prescaler);
            maximum_prescaler = maximum_prescaler.max(prescaler);
            maximum_pending = maximum_pending.max(unsafe { telemetry_pending_count(&telemetry) });
        }
    }

    assert!(maximum_prescaler - minimum_prescaler <= 8);
    assert!(maximum_pending < QUEUE_CAPACITY);
}

#[test]
fn multiple_channels_are_packed_by_slot() {
    let mut queue = [0_u8; 96];
    let mut telemetry = new_telemetry(&mut queue);
    let first = [1_u8, 2];
    let second = [3_u8, 4, 5, 6];

    assert_eq!(subscribe(&mut telemetry, 1, 0x1001, &second), TELEMETRY_OK);
    assert_eq!(subscribe(&mut telemetry, 0, 0x1000, &first), TELEMETRY_OK);
    assert_eq!(
        unsafe { telemetry_start(&mut telemetry, 1_000, 1, 0) },
        TELEMETRY_OK
    );
    assert_eq!(unsafe { telemetry_process(&mut telemetry, 1) }, 1);
    assert_eq!(read_frame(&mut telemetry), (1, [1, 2, 3, 4, 5, 6].to_vec()));
}

#[test]
fn reassigning_a_channel_updates_sample_size() {
    let mut queue = [0_u8; 96];
    let mut telemetry = new_telemetry(&mut queue);
    let first = [1_u8, 2, 3, 4];
    let second = [5_u8, 6];

    assert_eq!(subscribe(&mut telemetry, 0, 0x1000, &first), TELEMETRY_OK);
    assert_eq!(subscribe(&mut telemetry, 0, 0x1001, &second), TELEMETRY_OK);
    assert_eq!(unsafe { telemetry_sample_size(&telemetry) }, second.len());
}

#[test]
fn clearing_a_channel_removes_its_data() {
    let mut queue = [0_u8; 96];
    let mut telemetry = new_telemetry(&mut queue);
    let value = [1_u8, 2, 3, 4];

    assert_eq!(subscribe(&mut telemetry, 0, 0x1000, &value), TELEMETRY_OK);
    assert_eq!(
        unsafe {
            telemetry_subscribe(&mut telemetry, 0, TELEMETRY_NULL_INDEX, std::ptr::null(), 0)
        },
        TELEMETRY_OK
    );
    assert_eq!(unsafe { telemetry_sample_size(&telemetry) }, 0);
}

#[test]
fn invalid_direct_data_arguments_are_rejected() {
    let mut queue = [0_u8; 96];
    let mut telemetry = new_telemetry(&mut queue);
    let value = [1_u8, 2, 3, 4];

    assert_eq!(
        subscribe(&mut telemetry, TELEMETRY_MAX_CHANNELS as u16, 1, &value),
        TELEMETRY_INVALID_ARGUMENT
    );
    assert_eq!(
        unsafe { telemetry_subscribe(&mut telemetry, 0, 1, std::ptr::null(), value.len() as u16) },
        TELEMETRY_INVALID_ARGUMENT
    );
    assert_eq!(
        unsafe { telemetry_subscribe(&mut telemetry, 0, 1, value.as_ptr(), 0) },
        TELEMETRY_INVALID_ARGUMENT
    );
}

#[test]
fn processing_before_start_is_rejected() {
    let mut queue = [0_u8; 96];
    let mut telemetry = new_telemetry(&mut queue);
    let value = [1_u8, 2, 3, 4];

    assert_eq!(subscribe(&mut telemetry, 0, 1, &value), TELEMETRY_OK);
    assert_eq!(
        unsafe { telemetry_process(&mut telemetry, 1) },
        TELEMETRY_NOT_CONFIGURED
    );
}

#[test]
fn queue_without_capacity_rejects_start() {
    let mut queue = [0_u8; 8];
    let mut telemetry = new_telemetry(&mut queue);
    let value = [1_u8, 2, 3, 4];

    assert_eq!(subscribe(&mut telemetry, 0, 1, &value), TELEMETRY_OK);
    assert_eq!(
        unsafe { telemetry_start(&mut telemetry, 1_000, 1, 0) },
        TELEMETRY_FULL
    );
}

#[test]
fn empty_queue_returns_empty() {
    let mut queue = [0_u8; 96];
    let mut telemetry = new_telemetry(&mut queue);
    let value = [1_u8, 2, 3, 4];
    let mut timestamp = 0_u64;
    let mut data = [0_u8; 8];
    let mut data_size = 0_u16;

    assert_eq!(subscribe(&mut telemetry, 0, 1, &value), TELEMETRY_OK);
    assert_eq!(
        unsafe { telemetry_start(&mut telemetry, 1_000, 1, 0) },
        TELEMETRY_OK
    );
    assert_eq!(
        unsafe {
            telemetry_read_frame(
                &mut telemetry,
                &mut timestamp,
                data.as_mut_ptr(),
                data.len(),
                &mut data_size,
            )
        },
        TELEMETRY_EMPTY
    );
    assert_eq!(unsafe { telemetry_pending_count(&telemetry) }, 0);
}

#[test]
fn null_telemetry_is_rejected() {
    let mut queue = [0_u8; 96];
    assert_eq!(
        unsafe {
            telemetry_init(
                std::ptr::null_mut(),
                queue.as_mut_ptr(),
                queue.len(),
                std::ptr::null(),
            )
        },
        TELEMETRY_INVALID_ARGUMENT
    );
}

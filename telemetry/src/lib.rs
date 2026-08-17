//! Python bindings for the adaptive telemetry engine.

use std::ffi::c_void;
use std::sync::{Mutex, MutexGuard};

use pyo3::exceptions::{PyMemoryError, PyRuntimeError, PyValueError};
use pyo3::prelude::*;

/// Maximum number of channel slots exposed by the telemetry engine.
const CHANNEL_COUNT: usize = 16;
/// Maximum packed raw payload accepted by one telemetry frame.
const MAX_SAMPLE_SIZE: usize = 128;
/// Queue storage overhead for one timestamped frame.
const FRAME_TIMESTAMP_SIZE: usize = std::mem::size_of::<u64>();
/// C status returned when the telemetry queue has no frame.
const TELEMETRY_EMPTY: i32 = -6;
/// Register index used by the C API to clear a channel.
const TELEMETRY_NULL_INDEX: u16 = 0;

/// C representation of one mapped telemetry channel.
#[repr(C)]
struct TelemetryChannel {
    /// Dictionary index assigned to the channel.
    index: u16,
    /// Number of bytes copied from the mapped value.
    value_size: u16,
    /// Pointer to the caller-owned mapped value.
    data: *const u8,
}

/// C synchronization callbacks embedded in the telemetry state.
#[repr(C)]
struct TelemetrySync {
    /// Optional critical-section entry callback.
    enter: Option<unsafe extern "C" fn(*mut c_void) -> usize>,
    /// Optional critical-section exit callback.
    exit: Option<unsafe extern "C" fn(*mut c_void, usize)>,
    /// Opaque callback context.
    context: *mut c_void,
}

/// Rust representation of the C telemetry state.
#[repr(C)]
struct Telemetry {
    /// Mapped channel slots.
    channels: [TelemetryChannel; CHANNEL_COUNT],
    /// Base loop frequency in hertz.
    base_frequency_hz: u32,
    /// Current sampling divider.
    prescaler: u32,
    /// Configured lower-bound divider.
    configured_prescaler: u32,
    /// Tick at which the next frame is due.
    next_due_tick: u64,
    /// Caller-owned circular queue storage.
    queue_storage: *mut u8,
    /// Size of the queue storage in bytes.
    queue_storage_size: usize,
    /// Number of frame positions available in the queue storage.
    queue_capacity: usize,
    /// Index of the oldest queued frame.
    queue_head: usize,
    /// Number of queued frames.
    queue_count: usize,
    /// Packed payload size of one frame.
    sample_size: usize,
    /// Whether sampling is active.
    running: bool,
    /// Whether adaptive-rate control is enabled.
    adaptive_rate: bool,
    /// Fixed-point smoothed queue occupancy.
    adaptive_occupancy_q8: u32,
    /// Tick at which adaptive control is next evaluated.
    adaptive_next_update_tick: u64,
    /// Platform synchronization callbacks.
    sync: TelemetrySync,
}

unsafe extern "C" {
    /// Initializes a caller-owned telemetry state and queue storage.
    fn telemetry_init(
        telemetry: *mut Telemetry,
        queue_storage: *mut u8,
        queue_storage_size: usize,
        sync: *const TelemetrySync,
    ) -> i32;
    /// Assigns or clears one mapped channel.
    fn telemetry_subscribe(
        telemetry: *mut Telemetry,
        channel: u16,
        register_index: u16,
        data: *const u8,
        value_size: u16,
    ) -> i32;
    /// Enables or disables adaptive-rate control while stopped.
    fn telemetry_set_adaptive_rate(telemetry: *mut Telemetry, enabled: bool) -> i32;
    /// Starts sampling with the requested base frequency and divider.
    fn telemetry_start(
        telemetry: *mut Telemetry,
        base_frequency_hz: u32,
        prescaler: u32,
        now_tick: u64,
    ) -> i32;
    /// Processes one base-loop tick.
    fn telemetry_process(telemetry: *mut Telemetry, now_tick: u64) -> i32;
    /// Reads the oldest queued frame.
    fn telemetry_read_frame(
        telemetry: *mut Telemetry,
        timestamp_tick: *mut u64,
        data: *mut u8,
        data_capacity: usize,
        data_size: *mut u16,
    ) -> i32;
    /// Stops sampling and clears queued frames.
    fn telemetry_stop(telemetry: *mut Telemetry);
    /// Returns the packed payload size.
    fn telemetry_sample_size(telemetry: *const Telemetry) -> usize;
    /// Returns the number of queued frames.
    fn telemetry_pending_count(telemetry: *const Telemetry) -> usize;
    /// Returns the current effective divider.
    fn telemetry_get_prescaler(telemetry: *const Telemetry) -> u32;
    /// Returns whether adaptive-rate control is enabled.
    fn telemetry_get_adaptive_rate(telemetry: *const Telemetry) -> bool;
}

/// Owns one C telemetry state, its queue storage, and mapped channel values.
struct EngineState {
    /// C telemetry state whose pointers are backed by the other fields.
    telemetry: Telemetry,
    /// Fixed allocation retained for the lifetime of the C telemetry state.
    _queue_storage: Vec<u8>,
    /// Raw channel values retained at stable addresses for C mappings.
    channel_values: Vec<Vec<u8>>,
}

impl EngineState {
    /// Allocates and initializes a telemetry state with the requested capacity.
    fn new(queue_capacity: usize) -> PyResult<Self> {
        let frame_storage_size = FRAME_TIMESTAMP_SIZE + MAX_SAMPLE_SIZE;
        let queue_storage_size = queue_capacity
            .checked_mul(frame_storage_size)
            .ok_or_else(|| PyValueError::new_err("queue capacity is too large"))?;
        let mut queue_storage = Vec::new();
        queue_storage
            .try_reserve_exact(queue_storage_size)
            .map_err(|_| PyMemoryError::new_err("telemetry queue allocation failed"))?;
        queue_storage.resize(queue_storage_size, 0);

        // SAFETY: Telemetry contains only C-compatible integers, pointers,
        // nullable callbacks, and bool values. Zero is a valid pre-init state
        // for all of them, and telemetry_init initializes the complete object.
        let mut telemetry: Telemetry = unsafe { std::mem::zeroed() };
        // SAFETY: queue_storage remains allocated and unmoved for the lifetime
        // of the returned EngineState. The null sync pointer disables callbacks.
        let status = unsafe {
            telemetry_init(
                &mut telemetry,
                queue_storage.as_mut_ptr(),
                queue_storage.len(),
                std::ptr::null(),
            )
        };
        if status != 0 {
            return Err(PyRuntimeError::new_err(format!(
                "telemetry initialization failed with status {status}"
            )));
        }

        Ok(Self {
            telemetry,
            _queue_storage: queue_storage,
            channel_values: vec![Vec::new(); CHANNEL_COUNT],
        })
    }
}

// SAFETY: EngineState is accessed only while its containing mutex is held.
// The C state points into queue_storage and channel_values, which are never
// resized or moved after initialization while those pointers are registered.
unsafe impl Send for EngineState {}

impl Drop for EngineState {
    fn drop(&mut self) {
        // SAFETY: telemetry was initialized in EngineState::new and all calls
        // using its pointers are complete before fields are dropped.
        unsafe { telemetry_stop(&mut self.telemetry) };
    }
}

/// A Python-facing wrapper around the telemetry engine.
#[pyclass]
pub struct TelemetryEngine {
    /// Serializes C-engine access and protects channel buffer addresses.
    state: Mutex<EngineState>,
}

impl TelemetryEngine {
    /// Locks the engine state and converts a poisoned lock into a Python error.
    fn lock_state(&self) -> PyResult<MutexGuard<'_, EngineState>> {
        self.state
            .lock()
            .map_err(|_| PyRuntimeError::new_err("telemetry engine lock is poisoned"))
    }

    /// Converts a C status code into a Python exception.
    fn status_error(operation: &str, status: i32) -> PyErr {
        PyRuntimeError::new_err(format!("{operation} failed with telemetry status {status}"))
    }
}

#[pymethods]
impl TelemetryEngine {
    /// Creates an engine with a caller-selected number of frame slots.
    #[new]
    #[pyo3(signature = (queue_capacity = 256))]
    fn new(queue_capacity: usize) -> PyResult<Self> {
        if queue_capacity == 0 {
            return Err(PyValueError::new_err("queue_capacity must be positive"));
        }

        Ok(Self {
            state: Mutex::new(EngineState::new(queue_capacity)?),
        })
    }

    /// Assigns a raw value to one telemetry channel while stopped.
    fn set_channel(&self, channel: usize, dictionary_index: u16, value: &[u8]) -> PyResult<()> {
        if channel >= CHANNEL_COUNT {
            return Err(PyValueError::new_err(
                "channel is outside the supported range",
            ));
        }
        if dictionary_index == TELEMETRY_NULL_INDEX {
            return Err(PyValueError::new_err("dictionary_index must be non-zero"));
        }
        if value.is_empty() || value.len() > MAX_SAMPLE_SIZE {
            return Err(PyValueError::new_err(
                "channel value must contain between 1 and 128 bytes",
            ));
        }

        let mut state = self.lock_state()?;
        let new_channel_value = value.to_vec();
        let channel_u16 = u16::try_from(channel)
            .map_err(|_| PyValueError::new_err("channel does not fit the telemetry API"))?;
        let value_size = u16::try_from(value.len())
            .map_err(|_| PyValueError::new_err("channel value is too large"))?;
        let channel_data = new_channel_value.as_ptr();
        // SAFETY: telemetry and channel_data are valid while state is locked.
        // The channel buffer remains allocated until it is cleared or replaced.
        let status = unsafe {
            telemetry_subscribe(
                &mut state.telemetry,
                channel_u16,
                dictionary_index,
                channel_data,
                value_size,
            )
        };
        if status != 0 {
            return Err(Self::status_error("set_channel", status));
        }
        state.channel_values[channel] = new_channel_value;
        Ok(())
    }

    /// Removes one channel mapping while stopped.
    fn clear_channel(&self, channel: usize) -> PyResult<()> {
        if channel >= CHANNEL_COUNT {
            return Err(PyValueError::new_err(
                "channel is outside the supported range",
            ));
        }

        let mut state = self.lock_state()?;
        let channel_u16 = u16::try_from(channel)
            .map_err(|_| PyValueError::new_err("channel does not fit the telemetry API"))?;
        // SAFETY: telemetry is valid while state is locked. The C mapping is
        // cleared before the Rust-owned channel buffer is released.
        let status = unsafe {
            telemetry_subscribe(
                &mut state.telemetry,
                channel_u16,
                TELEMETRY_NULL_INDEX,
                std::ptr::null(),
                0,
            )
        };
        if status != 0 {
            return Err(Self::status_error("clear_channel", status));
        }
        state.channel_values[channel].clear();
        Ok(())
    }

    /// Updates the raw value behind an already configured channel.
    fn update_channel_value(&self, channel: usize, value: &[u8]) -> PyResult<()> {
        if channel >= CHANNEL_COUNT {
            return Err(PyValueError::new_err(
                "channel is outside the supported range",
            ));
        }
        if value.is_empty() || value.len() > MAX_SAMPLE_SIZE {
            return Err(PyValueError::new_err(
                "channel value must contain between 1 and 128 bytes",
            ));
        }

        let mut state = self.lock_state()?;
        if state.channel_values[channel].len() != value.len() {
            return Err(PyValueError::new_err(
                "updated channel value must keep its configured size",
            ));
        }
        state.channel_values[channel].copy_from_slice(value);
        Ok(())
    }

    /// Enables or disables queue-occupancy adaptive-rate control.
    fn set_adaptive_rate(&self, enabled: bool) -> PyResult<()> {
        let mut state = self.lock_state()?;
        // SAFETY: telemetry is valid while state is locked.
        let status = unsafe { telemetry_set_adaptive_rate(&mut state.telemetry, enabled) };
        if status != 0 {
            return Err(Self::status_error("set_adaptive_rate", status));
        }
        Ok(())
    }

    /// Starts sampling at the supplied base-loop frequency and divider.
    fn start(&self, base_frequency_hz: u32, prescaler: u32, now_tick: u64) -> PyResult<()> {
        let mut state = self.lock_state()?;
        // SAFETY: telemetry is valid while state is locked.
        let status = unsafe {
            telemetry_start(&mut state.telemetry, base_frequency_hz, prescaler, now_tick)
        };
        if status != 0 {
            return Err(Self::status_error("start", status));
        }
        Ok(())
    }

    /// Processes one base-loop tick and returns the C engine result code.
    fn process(&self, now_tick: u64) -> PyResult<i32> {
        let mut state = self.lock_state()?;
        // SAFETY: telemetry is valid while state is locked.
        Ok(unsafe { telemetry_process(&mut state.telemetry, now_tick) })
    }

    /// Reads the oldest queued frame, returning `None` when the queue is empty.
    fn read_frame(&self) -> PyResult<Option<(u64, Vec<u8>)>> {
        let mut state = self.lock_state()?;
        let sample_size =
            // SAFETY: telemetry is valid while state is locked.
            unsafe { telemetry_sample_size(&state.telemetry) };
        if sample_size > MAX_SAMPLE_SIZE {
            return Err(PyRuntimeError::new_err(
                "telemetry sample exceeds binding buffer",
            ));
        }

        let mut timestamp_tick = 0_u64;
        let mut data = [0_u8; MAX_SAMPLE_SIZE];
        let mut data_size = 0_u16;
        // SAFETY: output pointers refer to live, sufficiently sized local
        // buffers and telemetry is valid while state is locked.
        let status = unsafe {
            telemetry_read_frame(
                &mut state.telemetry,
                &mut timestamp_tick,
                data.as_mut_ptr(),
                data.len(),
                &mut data_size,
            )
        };
        if status == TELEMETRY_EMPTY {
            return Ok(None);
        }
        if status != 0 {
            return Err(Self::status_error("read_frame", status));
        }
        Ok(Some((
            timestamp_tick,
            data[..usize::from(data_size)].to_vec(),
        )))
    }

    /// Stops sampling and clears queued frames.
    fn stop(&self) -> PyResult<()> {
        let mut state = self.lock_state()?;
        // SAFETY: telemetry is valid while state is locked.
        unsafe { telemetry_stop(&mut state.telemetry) };
        Ok(())
    }

    /// Returns the packed payload size in bytes.
    #[getter]
    fn sample_size(&self) -> PyResult<usize> {
        let state = self.lock_state()?;
        // SAFETY: telemetry is valid while state is locked.
        Ok(unsafe { telemetry_sample_size(&state.telemetry) })
    }

    /// Returns the number of queued frames.
    #[getter]
    fn pending_count(&self) -> PyResult<usize> {
        let state = self.lock_state()?;
        // SAFETY: telemetry is valid while state is locked.
        Ok(unsafe { telemetry_pending_count(&state.telemetry) })
    }

    /// Returns the current effective sampling divider.
    #[getter]
    fn prescaler(&self) -> PyResult<u32> {
        let state = self.lock_state()?;
        // SAFETY: telemetry is valid while state is locked.
        Ok(unsafe { telemetry_get_prescaler(&state.telemetry) })
    }

    /// Returns whether adaptive-rate control is enabled.
    #[getter]
    fn adaptive_rate(&self) -> PyResult<bool> {
        let state = self.lock_state()?;
        // SAFETY: telemetry is valid while state is locked.
        Ok(unsafe { telemetry_get_adaptive_rate(&state.telemetry) })
    }
}

/// Registers the telemetry Python module.
#[pymodule]
fn telemetry(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<TelemetryEngine>()
}

//! `PyO3` bindings for telemetry decoder and recorder.

use std::sync::{Arc, Mutex, MutexGuard};

use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;

use super::channel::ChannelConfig;
use super::decoder::TelemetryDecoder;
use super::ipc_sink::TelemetryArrowIpcSink;
use super::parquet_recorder::TelemetryParquetRecorder;
use super::sink::TelemetrySink;
use crate::data_type_python::DataType;

/// Converts Python channel specifications into native telemetry channels.
fn channels_from_specs(specs: Vec<(String, String)>) -> PyResult<Vec<ChannelConfig>> {
    specs
        .into_iter()
        .map(|(identifier, dtype_name)| {
            let data_type = DataType::from_name(&dtype_name).ok_or_else(|| {
                PyValueError::new_err(format!("unsupported register data type: {dtype_name}"))
            })?;
            Ok(ChannelConfig::new(identifier, data_type))
        })
        .collect()
}

#[pyclass(name = "TelemetryParquetRecorder")]
/// Python-facing Parquet recorder.
pub struct PyTelemetryParquetRecorder {
    /// Native Parquet recorder.
    recorder: Mutex<Option<TelemetryParquetRecorder>>,
}

#[pyclass(name = "TelemetryArrowIpcSink")]
/// Python-facing Arrow IPC telemetry sink.
pub struct PyTelemetryArrowIpcSink {
    /// Native Arrow IPC sink.
    sink: Mutex<Option<TelemetryArrowIpcSink>>,
}

impl PyTelemetryArrowIpcSink {
    /// Locks the native sink slot and converts a poisoned lock into a Python error.
    fn lock(&self) -> PyResult<MutexGuard<'_, Option<TelemetryArrowIpcSink>>> {
        self.sink
            .lock()
            .map_err(|_| PyRuntimeError::new_err("telemetry IPC sink lock is poisoned"))
    }
}

impl PyTelemetryParquetRecorder {
    /// Locks the native recorder slot and converts a poisoned lock into a
    /// Python error.
    fn lock(&self) -> PyResult<MutexGuard<'_, Option<TelemetryParquetRecorder>>> {
        self.recorder
            .lock()
            .map_err(|_| PyRuntimeError::new_err("telemetry recorder lock is poisoned"))
    }
}

/// Python-facing handle for the shared Rust telemetry decoder.
#[pyclass(name = "TelemetryDecoder")]
pub struct PyTelemetryDecoder {
    /// Shared decoder worker.
    decoder: Arc<TelemetryDecoder>,
}

#[pymethods]
impl PyTelemetryDecoder {
    /// Creates and starts a decoder worker.
    #[new]
    #[pyo3(signature = (channel_specs, timestamp_frequency_hz, batch_size = 1000))]
    fn new(
        channel_specs: Vec<(String, String)>,
        timestamp_frequency_hz: f64,
        batch_size: usize,
    ) -> PyResult<Self> {
        let channels = channels_from_specs(channel_specs)?;
        let decoder = TelemetryDecoder::new(channels, timestamp_frequency_hz, batch_size)
            .map_err(|error| PyValueError::new_err(error.to_string()))?;
        Ok(Self {
            decoder: Arc::new(decoder),
        })
    }

    /// Attaches a Rust Parquet recorder as a decoded-sample sink.
    fn attach_sink(&self, recorder: &Bound<'_, PyTelemetryParquetRecorder>) -> PyResult<()> {
        let recorder = recorder
            .borrow_mut()
            .lock()
            .map_err(|_| PyRuntimeError::new_err("telemetry recorder lock is poisoned"))?
            .take()
            .ok_or_else(|| PyRuntimeError::new_err("telemetry recorder is already attached"))?;
        self.decoder
            .attach_sink(Box::new(recorder))
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    /// Attaches an Arrow IPC sink to the decoder worker.
    fn attach_ipc_sink(&self, sink: &Bound<'_, PyTelemetryArrowIpcSink>) -> PyResult<()> {
        let sink = sink
            .borrow_mut()
            .lock()
            .map_err(|_| PyRuntimeError::new_err("telemetry IPC sink lock is poisoned"))?
            .take()
            .ok_or_else(|| PyRuntimeError::new_err("telemetry IPC sink is already attached"))?;
        self.decoder
            .attach_sink(Box::new(sink))
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    /// Queues one raw complete-access response for decoding.
    fn feed(&self, access: &[u8]) -> PyResult<()> {
        self.decoder
            .feed(access)
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    /// Flushes pending samples while keeping the decoder usable.
    fn flush(&self) -> PyResult<()> {
        self.decoder
            .flush()
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    /// Adds a marker to every attached recording.
    fn add_marker(&self, label: &str, timestamp: Option<f64>, epoch: usize) -> PyResult<()> {
        self.decoder
            .add_marker(label, timestamp, epoch)
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    /// Stops the decoder worker after draining queued accesses.
    fn stop(&self) -> PyResult<()> {
        self.decoder
            .stop()
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }
}

#[pymethods]
impl PyTelemetryParquetRecorder {
    /// Creates a recorder and opens its Parquet output file.
    #[new]
    #[pyo3(signature = (path, channel_specs, timestamp_frequency_hz, requested_frequency_hz, achieved_frequency_hz, batch_size = 1000))]
    fn new(
        path: &str,
        channel_specs: Vec<(String, String)>,
        timestamp_frequency_hz: f64,
        requested_frequency_hz: f64,
        achieved_frequency_hz: f64,
        batch_size: usize,
    ) -> PyResult<Self> {
        let channels = channels_from_specs(channel_specs)?;
        let recorder = TelemetryParquetRecorder::new(
            path,
            channels,
            timestamp_frequency_hz,
            requested_frequency_hz,
            achieved_frequency_hz,
            batch_size,
        )
        .map_err(|error| PyValueError::new_err(error.to_string()))?;
        Ok(Self {
            recorder: Mutex::new(Some(recorder)),
        })
    }

    /// Adds a marker to the recording metadata.
    fn add_marker(&self, label: &str, timestamp: Option<f64>, epoch: usize) -> PyResult<()> {
        self.lock()?
            .as_mut()
            .ok_or_else(|| PyRuntimeError::new_err("telemetry recorder is already attached"))?
            .add_marker(label, timestamp, epoch)
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }

    /// Closes the Parquet file.
    fn close(&self) -> PyResult<()> {
        self.lock()?
            .as_mut()
            .ok_or_else(|| PyRuntimeError::new_err("telemetry recorder is already attached"))?
            .close()
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }
}

#[pymethods]
impl PyTelemetryArrowIpcSink {
    /// Creates an Arrow IPC sink listening for one local viewer connection.
    #[new]
    #[pyo3(signature = (address, channel_specs, timestamp_frequency_hz, requested_frequency_hz, achieved_frequency_hz))]
    fn new(
        address: &str,
        channel_specs: Vec<(String, String)>,
        timestamp_frequency_hz: f64,
        requested_frequency_hz: f64,
        achieved_frequency_hz: f64,
    ) -> PyResult<Self> {
        let channels = channels_from_specs(channel_specs)?;
        let sink = TelemetryArrowIpcSink::new(
            address,
            channels,
            timestamp_frequency_hz,
            requested_frequency_hz,
            achieved_frequency_hz,
        )
        .map_err(|error| PyValueError::new_err(error.to_string()))?;
        Ok(Self {
            sink: Mutex::new(Some(sink)),
        })
    }

    /// Returns the listening address, including an OS-assigned port when applicable.
    #[getter]
    fn address(&self) -> PyResult<String> {
        Ok(self
            .lock()?
            .as_ref()
            .ok_or_else(|| PyRuntimeError::new_err("telemetry IPC sink is already attached"))?
            .address()
            .to_string())
    }

    /// Closes the Arrow IPC stream and listener.
    fn close(&self) -> PyResult<()> {
        self.lock()?
            .as_mut()
            .ok_or_else(|| PyRuntimeError::new_err("telemetry IPC sink is already attached"))?
            .close()
            .map_err(|error| PyRuntimeError::new_err(error.to_string()))
    }
}

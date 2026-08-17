//! Asynchronous Arrow IPC telemetry streaming over a local TCP listener.

use std::io::{ErrorKind, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::Arc;
use std::sync::mpsc::{self, Receiver, SyncSender, TrySendError};
use std::thread::{self, JoinHandle};
use std::time::Duration;

use arrow_array::builder::{Float64Builder, UInt64Builder};
use arrow_array::{ArrayRef, Float64Array, RecordBatch};
use arrow_ipc::writer::StreamWriter;
use arrow_schema::{DataType as ArrowDataType, Field, Schema};

use super::arrow::{channel_arrow_type, new_channel_appender};
use super::channel::ChannelConfig;
use super::error::RecorderError;
use super::sample::DecodedSample;
use super::sink::TelemetrySink;

/// Work item sent from the decoder to the IPC writer thread.
enum IpcMessage {
    /// A decoded telemetry batch.
    Samples(Vec<DecodedSample>),
    /// Requests an orderly writer shutdown.
    Close,
}

/// Arrow IPC sink with a bounded, non-blocking producer queue.
pub(super) struct TelemetryArrowIpcSink {
    /// Bounded queue used by the decoder worker.
    sender: SyncSender<IpcMessage>,
    /// Writer thread that owns the listener and TCP stream.
    writer: Option<JoinHandle<()>>,
    /// Bound listener address.
    address: std::net::SocketAddr,
}

impl TelemetryArrowIpcSink {
    /// Creates a non-blocking TCP listener and asynchronous Arrow writer.
    ///
    /// # Errors
    ///
    /// Returns an error when the address cannot be parsed or bound.
    pub(super) fn new(
        address: &str,
        channels: Vec<ChannelConfig>,
        timestamp_frequency_hz: f64,
        requested_frequency_hz: f64,
        achieved_frequency_hz: f64,
    ) -> Result<Self, RecorderError> {
        let listener = TcpListener::bind(address)
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        listener
            .set_nonblocking(true)
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        let address = listener
            .local_addr()
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        let schema = Arc::new(schema(
            &channels,
            timestamp_frequency_hz,
            requested_frequency_hz,
            achieved_frequency_hz,
        ));
        let (sender, receiver) = mpsc::sync_channel(8);
        let writer = thread::Builder::new()
            .name("TelemetryArrowIpcSink-writer".to_string())
            .spawn(move || writer_loop(listener, receiver, schema, channels))
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        Ok(Self {
            sender,
            writer: Some(writer),
            address,
        })
    }

    /// Returns the address on which the viewer can connect.
    pub(super) fn address(&self) -> std::net::SocketAddr {
        self.address
    }
}

impl TelemetrySink for TelemetryArrowIpcSink {
    /// Queues a decoded batch without blocking the decoder.
    fn write_samples(&mut self, samples: &[DecodedSample]) -> Result<(), RecorderError> {
        if samples.is_empty() {
            return Ok(());
        }
        match self.sender.try_send(IpcMessage::Samples(samples.to_vec())) {
            Ok(()) | Err(TrySendError::Full(_)) => Ok(()),
            Err(TrySendError::Disconnected(_)) => Err(RecorderError::Parquet(
                "IPC writer thread stopped".to_string(),
            )),
        }
    }

    /// Markers are not encoded in the fixed-schema IPC stream.
    fn add_marker(
        &mut self,
        _label: &str,
        _timestamp: Option<f64>,
        _epoch: usize,
    ) -> Result<(), RecorderError> {
        Ok(())
    }

    /// Stops the writer thread after draining queued batches.
    fn close(&mut self) -> Result<(), RecorderError> {
        if self.writer.is_some() {
            let _ = self.sender.send(IpcMessage::Close);
        }
        if let Some(writer) = self.writer.take() {
            writer
                .join()
                .map_err(|_| RecorderError::Parquet("IPC writer thread panicked".to_string()))?;
        }
        Ok(())
    }
}

/// Runs the isolated IPC writer and viewer accept loop.
fn writer_loop(
    listener: TcpListener,
    receiver: Receiver<IpcMessage>,
    schema: Arc<Schema>,
    channels: Vec<ChannelConfig>,
) {
    let mut writer: Option<StreamWriter<TcpStream>> = None;
    loop {
        match receiver.recv_timeout(Duration::from_millis(10)) {
            Ok(IpcMessage::Samples(samples)) => {
                accept_viewer(&listener, &schema, &mut writer);
                if let Some(active_writer) = writer.as_mut() {
                    let result = record_batch(&schema, &channels, &samples)
                        .and_then(|batch| write_batch(active_writer, &batch));
                    if result.is_err() {
                        writer = None;
                    }
                }
            }
            Ok(IpcMessage::Close) => break,
            Err(mpsc::RecvTimeoutError::Timeout) => {
                accept_viewer(&listener, &schema, &mut writer);
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }
    if let Some(mut active_writer) = writer {
        let _ = active_writer.finish();
    }
}

/// Accepts a viewer and writes the stream schema when one is waiting.
fn accept_viewer(
    listener: &TcpListener,
    schema: &Arc<Schema>,
    writer: &mut Option<StreamWriter<TcpStream>>,
) {
    if writer.is_some() {
        return;
    }
    match listener.accept() {
        Ok((stream, _)) => {
            if stream.set_nodelay(true).is_ok() {
                *writer = StreamWriter::try_new(stream, schema).ok();
            }
        }
        Err(error) if error.kind() == ErrorKind::WouldBlock => {}
        Err(_) => {}
    }
}

/// Builds one typed Arrow record batch from decoded samples.
fn record_batch(
    schema: &Arc<Schema>,
    channels: &[ChannelConfig],
    samples: &[DecodedSample],
) -> Result<RecordBatch, RecorderError> {
    let mut timestamp = Float64Builder::with_capacity(samples.len());
    let mut drive_timestamp = Float64Builder::with_capacity(samples.len());
    let mut timestamp_segment = UInt64Builder::with_capacity(samples.len());
    let mut channel_builders = channels
        .iter()
        .enumerate()
        .map(|(index, channel)| new_channel_appender(channel, samples.len(), index))
        .collect::<Result<Vec<_>, _>>()?;
    for sample in samples {
        timestamp.append_value(sample.timestamp);
        drive_timestamp.append_value(sample.drive_timestamp);
        timestamp_segment.append_value(sample.timestamp_segment);
        for (index, value) in sample.values.iter().enumerate() {
            channel_builders[index]
                .append_value(value)
                .map_err(|error| match error {
                    RecorderError::ChannelTypeMismatch { .. } => {
                        RecorderError::ChannelTypeMismatch { channel: index }
                    }
                    error => error,
                })?;
        }
    }
    let mut columns: Vec<ArrayRef> = vec![
        Arc::new(timestamp.finish()),
        Arc::new(drive_timestamp.finish()),
        Arc::new(timestamp_segment.finish()),
        Arc::new(Float64Array::from(vec![None; samples.len()])),
    ];
    columns.extend(
        channel_builders
            .into_iter()
            .map(|mut builder| builder.finish()),
    );
    RecordBatch::try_new(Arc::clone(schema), columns)
        .map_err(|error| RecorderError::Parquet(error.to_string()))
}

/// Writes one batch and flushes it to the viewer.
fn write_batch(
    writer: &mut StreamWriter<TcpStream>,
    batch: &RecordBatch,
) -> Result<(), RecorderError> {
    writer
        .write(batch)
        .map_err(|error| RecorderError::Parquet(error.to_string()))?;
    writer
        .get_mut()
        .flush()
        .map_err(|error| RecorderError::Parquet(error.to_string()))
}

/// Builds the schema shared with the Parquet representation.
fn schema(
    channels: &[ChannelConfig],
    timestamp_frequency_hz: f64,
    requested_frequency_hz: f64,
    achieved_frequency_hz: f64,
) -> Schema {
    let mut fields = vec![
        Field::new("timestamp", ArrowDataType::Float64, false),
        Field::new("drive_timestamp", ArrowDataType::Float64, false),
        Field::new("timestamp_segment", ArrowDataType::UInt64, false),
        Field::new("host_time", ArrowDataType::Float64, true),
    ];
    fields.extend(
        channels
            .iter()
            .map(|channel| Field::new(&channel.identifier, channel_arrow_type(channel), true)),
    );
    let mut metadata = std::collections::HashMap::new();
    metadata.insert(
        "ingenialink.telemetry.format_version".to_string(),
        "2".to_string(),
    );
    metadata.insert(
        "ingenialink.telemetry.timestamp_tick_frequency_hz".to_string(),
        timestamp_frequency_hz.to_string(),
    );
    metadata.insert(
        "ingenialink.telemetry.requested_frequency_hz".to_string(),
        requested_frequency_hz.to_string(),
    );
    metadata.insert(
        "ingenialink.telemetry.achieved_frequency_hz".to_string(),
        achieved_frequency_hz.to_string(),
    );
    Schema::new_with_metadata(fields, metadata)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data_type::ByteOrder;
    use crate::data_type_python::DataType;
    use crate::telemetry::sample::DecodedValue;
    use arrow_array::{Array, UInt16Array};
    use arrow_ipc::reader::StreamReader;

    fn channel() -> ChannelConfig {
        ChannelConfig {
            identifier: "speed".to_string(),
            data_type: DataType::U16,
            byte_order: ByteOrder::Little,
        }
    }

    fn sample() -> DecodedSample {
        DecodedSample {
            timestamp: 1.0,
            drive_timestamp: 1.0,
            timestamp_segment: 0,
            values: vec![DecodedValue::U16(42)],
        }
    }

    #[test]
    fn streams_decoded_samples_as_arrow_batches() -> Result<(), RecorderError> {
        let mut sink = TelemetryArrowIpcSink::new(
            "127.0.0.1:0",
            vec![channel()],
            1_000_000.0,
            1_000.0,
            1_000.0,
        )?;
        let client = TcpStream::connect(sink.address())
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        sink.write_samples(&[sample()])?;
        sink.close()?;
        let mut reader = StreamReader::try_new(client, None)
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        let batch = reader
            .next()
            .ok_or_else(|| RecorderError::Parquet("Arrow stream was empty".to_string()))?
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        let values = batch
            .column(4)
            .as_any()
            .downcast_ref::<UInt16Array>()
            .ok_or_else(|| RecorderError::Parquet("unexpected Arrow channel type".to_string()))?;
        assert_eq!(values.value(0), 42);
        Ok(())
    }

    #[test]
    fn drops_batches_when_viewer_queue_is_full() -> Result<(), RecorderError> {
        let sink = TelemetryArrowIpcSink::new(
            "127.0.0.1:0",
            vec![channel()],
            1_000_000.0,
            1_000.0,
            1_000.0,
        )?;
        let sender = sink.sender.clone();
        for _ in 0..32 {
            let _ = sender.try_send(IpcMessage::Samples(vec![sample()]));
        }
        drop(sink);
        Ok(())
    }
}

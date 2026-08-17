//! Telemetry frame decoding and decoded-sample fan-out.

use std::sync::{Mutex, mpsc};
use std::thread::{self, JoinHandle};

use super::channel::ChannelConfig;
use super::error::RecorderError;
use super::sample::{DecodedSample, DecodedValue};
use super::sink::TelemetrySink;
use crate::data_type::{Bool, ByteArray512, ByteOrder, CodecError, F32, FixedDataType};
use crate::data_type::{S8, S16, S32, S64, U8, U16, U32, U64};
use crate::data_type_python::DataType;

/// Size of the complete-access frame-count prefix.
const FRAME_COUNT_SIZE: usize = 2;
/// Size of one firmware timestamp.
const TIMESTAMP_SIZE: usize = 8;

/// Decodes complete-access frames into Rust-native telemetry samples.
pub(super) struct TelemetryDecoderCore {
    /// Configured channels and their payload offsets.
    channels: Vec<(ChannelConfig, usize)>,
    /// Firmware timestamp frequency.
    timestamp_frequency_hz: f64,
    /// Most recent firmware timestamp in seconds.
    last_drive_timestamp: Option<f64>,
    /// Offset used to keep timestamps continuous across resets.
    timestamp_offset: f64,
    /// Current firmware timestamp segment.
    timestamp_segment: u64,
    /// Smallest timestamp step used when normalizing resets.
    timestamp_step: f64,
}

impl TelemetryDecoderCore {
    /// Creates a decoder for a fixed channel layout.
    pub(super) fn new(
        channels: &[ChannelConfig],
        timestamp_frequency_hz: f64,
    ) -> Result<Self, RecorderError> {
        if !timestamp_frequency_hz.is_finite() || timestamp_frequency_hz <= 0.0 {
            return Err(RecorderError::InvalidConfiguration {
                field: "timestamp_frequency_hz",
            });
        }
        let mut offset = 0;
        let mut layout = Vec::with_capacity(channels.len());
        for (channel_index, channel) in channels.iter().enumerate() {
            let size = channel
                .byte_length()
                .ok_or(RecorderError::VariableChannel {
                    channel: channel_index,
                })?;
            layout.push((channel.clone(), offset));
            offset += size;
        }
        Ok(Self {
            channels: layout,
            timestamp_frequency_hz,
            last_drive_timestamp: None,
            timestamp_offset: 0.0,
            timestamp_segment: 0,
            timestamp_step: 1.0 / timestamp_frequency_hz,
        })
    }

    /// Decodes one complete-access response.
    ///
    /// # Errors
    ///
    /// Returns an error when the response is truncated or a channel payload
    /// does not match its configured data type.
    pub(super) fn feed(&mut self, access: &[u8]) -> Result<Vec<DecodedSample>, RecorderError> {
        if access.len() < FRAME_COUNT_SIZE {
            return Ok(Vec::new());
        }
        let frame_count = usize::from(u16::from_le_bytes([access[0], access[1]]));
        let payload_size = self
            .channels
            .iter()
            .map(|(channel, _)| channel.byte_length().unwrap_or(0))
            .sum::<usize>();
        let frame_size = TIMESTAMP_SIZE + payload_size;
        let expected = FRAME_COUNT_SIZE.saturating_add(frame_count.saturating_mul(frame_size));
        if access.len() < expected {
            return Err(RecorderError::TruncatedAccess {
                frame_count,
                expected,
                actual: access.len(),
            });
        }

        let mut samples = Vec::with_capacity(frame_count);
        for frame_index in 0..frame_count {
            let frame_offset = FRAME_COUNT_SIZE + frame_index * frame_size;
            let timestamp_end = frame_offset + TIMESTAMP_SIZE;
            let timestamp_tick =
                u64::from_le_bytes(access[frame_offset..timestamp_end].try_into().map_err(
                    |_| RecorderError::InvalidSampleSize {
                        actual: 0,
                        expected: payload_size,
                    },
                )?);
            let payload = &access[timestamp_end..timestamp_end + payload_size];
            let values = self.decode_frame(payload, payload_size)?;
            let drive_timestamp = timestamp_tick as f64 / self.timestamp_frequency_hz;
            if let Some(last_drive_timestamp) = self.last_drive_timestamp
                && drive_timestamp < last_drive_timestamp
            {
                self.timestamp_segment += 1;
                self.timestamp_offset +=
                    (last_drive_timestamp + self.timestamp_step) - drive_timestamp;
            }
            let timestamp = drive_timestamp + self.timestamp_offset;
            self.last_drive_timestamp = Some(drive_timestamp);
            samples.push(DecodedSample {
                timestamp,
                drive_timestamp,
                timestamp_segment: self.timestamp_segment,
                values,
            });
        }
        Ok(samples)
    }

    /// Decodes the channel payload of one frame.
    fn decode_frame(
        &self,
        payload: &[u8],
        expected_size: usize,
    ) -> Result<Vec<DecodedValue>, RecorderError> {
        if payload.len() != expected_size {
            return Err(RecorderError::InvalidSampleSize {
                actual: payload.len(),
                expected: expected_size,
            });
        }
        self.channels
            .iter()
            .enumerate()
            .map(|(channel_index, (channel, offset))| {
                let size = channel.byte_length().unwrap_or(0);
                decode_value(
                    channel.data_type,
                    &payload[*offset..*offset + size],
                    channel.byte_order,
                )
                .map_err(|source| RecorderError::Decode {
                    channel: channel_index,
                    source,
                })
            })
            .collect()
    }
}

/// Parses one fixed-width value in the selected byte order.
fn parse_fixed<T: FixedDataType>(
    data: &[u8],
    byte_order: ByteOrder,
) -> Result<T::Value, CodecError> {
    match byte_order {
        ByteOrder::Little => T::parse(data),
        ByteOrder::Big => T::parse_be(data),
    }
}

/// Converts one channel payload into a Rust-native value.
fn decode_value(
    data_type: DataType,
    data: &[u8],
    byte_order: ByteOrder,
) -> Result<DecodedValue, CodecError> {
    Ok(match data_type {
        DataType::U8 => DecodedValue::U8(parse_fixed::<U8>(data, byte_order)?),
        DataType::S8 => DecodedValue::S8(parse_fixed::<S8>(data, byte_order)?),
        DataType::U16 => DecodedValue::U16(parse_fixed::<U16>(data, byte_order)?),
        DataType::S16 => DecodedValue::S16(parse_fixed::<S16>(data, byte_order)?),
        DataType::U32 => DecodedValue::U32(parse_fixed::<U32>(data, byte_order)?),
        DataType::S32 => DecodedValue::S32(parse_fixed::<S32>(data, byte_order)?),
        DataType::U64 => DecodedValue::U64(parse_fixed::<U64>(data, byte_order)?),
        DataType::S64 => DecodedValue::S64(parse_fixed::<S64>(data, byte_order)?),
        DataType::Float => DecodedValue::Float(parse_fixed::<F32>(data, byte_order)?),
        DataType::Bool => DecodedValue::Bool(parse_fixed::<Bool>(data, byte_order)?),
        DataType::ByteArray512 => {
            DecodedValue::ByteArray512(Box::new(parse_fixed::<ByteArray512>(data, byte_order)?))
        }
        DataType::Str => {
            return Err(CodecError::InvalidBufferLength {
                expected: 0,
                got: 0,
            });
        }
    })
}

/// Message processed by the decoder worker.
enum DecoderMessage {
    /// Queues a raw complete-access response.
    Feed(Vec<u8>),
    /// Transfers ownership of a Parquet sink to the worker.
    AddSink(Box<dyn TelemetrySink>),
    /// Flushes pending samples while keeping the worker open.
    Flush(mpsc::Sender<Result<(), RecorderError>>),
    /// Adds a marker to every attached sink.
    AddMarker {
        /// Marker label.
        label: String,
        /// Optional marker timestamp.
        timestamp: Option<f64>,
        /// Connection epoch associated with the marker.
        epoch: usize,
        /// Response channel for the command result.
        response: mpsc::Sender<Result<(), RecorderError>>,
    },
    /// Flushes and closes all sinks.
    Close(mpsc::Sender<Result<(), RecorderError>>),
}

/// Rust decoder that fans decoded samples out to attached sinks.
pub struct TelemetryDecoder {
    /// Sender used by transport and control callers.
    sender: mpsc::Sender<DecoderMessage>,
    /// Worker handle retained for shutdown and joining.
    worker: Mutex<Option<JoinHandle<Result<(), RecorderError>>>>,
}

impl TelemetryDecoder {
    /// Creates and starts a decoder worker.
    ///
    /// # Errors
    ///
    /// Returns an error when the channel configuration is invalid.
    pub fn new(
        channels: Vec<ChannelConfig>,
        timestamp_frequency_hz: f64,
        batch_size: usize,
    ) -> Result<Self, RecorderError> {
        if batch_size == 0 {
            return Err(RecorderError::InvalidConfiguration {
                field: "batch_size",
            });
        }
        let (sender, receiver) = mpsc::channel();
        let worker = thread::spawn(move || {
            let mut decoder = TelemetryDecoderCore::new(&channels, timestamp_frequency_hz)?;
            let mut pending = Vec::new();
            let mut sinks = Vec::new();
            while let Ok(message) = receiver.recv() {
                match message {
                    DecoderMessage::Feed(access) => {
                        pending.extend(decoder.feed(&access)?);
                        while pending.len() >= batch_size {
                            let batch = pending.drain(..batch_size).collect::<Vec<_>>();
                            write_samples(&mut sinks, &batch)?;
                        }
                    }
                    DecoderMessage::AddSink(sink) => sinks.push(sink),
                    DecoderMessage::Flush(response) => {
                        let result = flush_decoder(&mut pending, &mut sinks);
                        let _ = response.send(result);
                    }
                    DecoderMessage::AddMarker {
                        label,
                        timestamp,
                        epoch,
                        response,
                    } => {
                        let result = sinks
                            .iter_mut()
                            .try_for_each(|sink| sink.add_marker(&label, timestamp, epoch));
                        let _ = response.send(result);
                    }
                    DecoderMessage::Close(response) => {
                        let result = close_decoder(&mut pending, &mut sinks);
                        let _ = response.send(result);
                        break;
                    }
                }
            }
            Ok(())
        });
        Ok(Self {
            sender,
            worker: Mutex::new(Some(worker)),
        })
    }

    /// Transfers a generic sink to the decoder worker.
    ///
    /// # Errors
    ///
    /// Returns an error when the decoder worker is unavailable.
    pub(super) fn attach_sink(&self, sink: Box<dyn TelemetrySink>) -> Result<(), RecorderError> {
        self.sender
            .send(DecoderMessage::AddSink(sink))
            .map_err(|error| RecorderError::Parquet(error.to_string()))
    }

    /// Queues one raw complete-access response for decoding.
    ///
    /// # Errors
    ///
    /// Returns an error when the decoder worker is unavailable.
    pub fn feed(&self, access: &[u8]) -> Result<(), RecorderError> {
        self.sender
            .send(DecoderMessage::Feed(access.to_vec()))
            .map_err(|error| RecorderError::Parquet(error.to_string()))
    }

    /// Flushes pending samples while keeping the decoder usable.
    ///
    /// # Errors
    ///
    /// Returns an error when the worker or a sink fails.
    pub fn flush(&self) -> Result<(), RecorderError> {
        self.request(DecoderMessage::Flush)
    }

    /// Adds a marker to every attached recording.
    ///
    /// # Errors
    ///
    /// Returns an error when the worker or a sink fails.
    pub fn add_marker(
        &self,
        label: &str,
        timestamp: Option<f64>,
        epoch: usize,
    ) -> Result<(), RecorderError> {
        let (response_sender, response_receiver) = mpsc::channel();
        self.sender
            .send(DecoderMessage::AddMarker {
                label: label.to_string(),
                timestamp,
                epoch,
                response: response_sender,
            })
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        response_receiver
            .recv()
            .map_err(|error| RecorderError::Parquet(error.to_string()))?
    }

    /// Stops the worker after draining queued accesses.
    ///
    /// # Errors
    ///
    /// Returns an error when the worker or a sink fails.
    pub fn stop(&self) -> Result<(), RecorderError> {
        let result = self.request(DecoderMessage::Close);
        if let Some(worker) = self
            .worker
            .lock()
            .map_err(|_| RecorderError::Parquet("decoder worker lock poisoned".to_string()))?
            .take()
        {
            worker
                .join()
                .map_err(|_| RecorderError::Parquet("decoder worker panicked".to_string()))??;
        }
        result
    }

    /// Sends a worker command and waits for its result.
    fn request(
        &self,
        message: impl FnOnce(mpsc::Sender<Result<(), RecorderError>>) -> DecoderMessage,
    ) -> Result<(), RecorderError> {
        let (response_sender, response_receiver) = mpsc::channel();
        self.sender
            .send(message(response_sender))
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        response_receiver
            .recv()
            .map_err(|error| RecorderError::Parquet(error.to_string()))?
    }
}

/// Writes decoded samples to every attached sink.
fn write_samples(
    sinks: &mut [Box<dyn TelemetrySink>],
    samples: &[DecodedSample],
) -> Result<(), RecorderError> {
    sinks
        .iter_mut()
        .try_for_each(|sink| sink.write_samples(samples))
}

/// Flushes pending decoded samples to every attached sink.
fn flush_decoder(
    pending: &mut Vec<DecodedSample>,
    sinks: &mut [Box<dyn TelemetrySink>],
) -> Result<(), RecorderError> {
    if pending.is_empty() {
        return Ok(());
    }
    write_samples(sinks, pending)?;
    pending.clear();
    Ok(())
}

/// Flushes pending samples and closes every attached sink.
fn close_decoder(
    pending: &mut Vec<DecodedSample>,
    sinks: &mut [Box<dyn TelemetrySink>],
) -> Result<(), RecorderError> {
    flush_decoder(pending, sinks)?;
    sinks.iter_mut().try_for_each(|sink| sink.close())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn channel(data_type: DataType) -> ChannelConfig {
        ChannelConfig {
            identifier: "test".to_string(),
            data_type,
            byte_order: ByteOrder::Little,
        }
    }

    #[test]
    fn decodes_timestamp_and_native_channel_values() -> Result<(), RecorderError> {
        let mut decoder = TelemetryDecoderCore::new(
            &[channel(DataType::U16), channel(DataType::S8)],
            1_000_000.0,
        )?;
        let mut access = vec![1, 0];
        access.extend_from_slice(&2_000_000_u64.to_le_bytes());
        access.extend_from_slice(&513_u16.to_le_bytes());
        access.push(254);

        let samples = decoder.feed(&access)?;
        assert_eq!(samples.len(), 1);
        assert_eq!(samples[0].timestamp, 2.0);
        assert_eq!(
            samples[0].values,
            vec![DecodedValue::U16(513), DecodedValue::S8(-2)]
        );
        Ok(())
    }

    #[test]
    fn timestamp_reset_starts_a_new_segment() -> Result<(), RecorderError> {
        let mut decoder = TelemetryDecoderCore::new(&[channel(DataType::U8)], 1_000_000.0)?;
        let mut access = vec![2, 0];
        access.extend_from_slice(&2_000_000_u64.to_le_bytes());
        access.push(1);
        access.extend_from_slice(&1_000_u64.to_le_bytes());
        access.push(2);

        let samples = decoder.feed(&access)?;
        assert_eq!(samples[0].timestamp_segment, 0);
        assert_eq!(samples[1].timestamp_segment, 1);
        assert_eq!(samples[1].timestamp, 2.000001);
        Ok(())
    }
}

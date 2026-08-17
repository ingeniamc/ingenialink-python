//! Arrow-to-Parquet telemetry recording.

use std::fs::File;
use std::path::Path;
use std::sync::Arc;
use std::time::{SystemTime, UNIX_EPOCH};

use arrow_array::builder::{Float64Builder, UInt64Builder};
use arrow_array::{ArrayRef, Float64Array, RecordBatch};
use arrow_schema::{DataType as ArrowDataType, Field, Schema};
use parquet::arrow::ArrowWriter;
use parquet::file::metadata::KeyValue;
use parquet::file::properties::WriterProperties;

use super::arrow::{ChannelAppender, channel_arrow_type, new_channel_appender};
use super::channel::ChannelConfig;
use super::error::RecorderError;
use super::sample::DecodedSample;
use super::sink::TelemetrySink;

/// Metadata key for the recording format version.
const FORMAT_VERSION_KEY: &str = "ingenialink.telemetry.format_version";
/// Metadata key for the recording start time.
const START_TIME_KEY: &str = "ingenialink.telemetry.recording_start_utc";
/// Metadata key for firmware timestamp frequency.
const TICK_FREQUENCY_KEY: &str = "ingenialink.telemetry.timestamp_tick_frequency_hz";
/// Metadata key for requested sampling frequency.
const REQUESTED_FREQUENCY_KEY: &str = "ingenialink.telemetry.requested_frequency_hz";
/// Metadata key for achieved sampling frequency.
const ACHIEVED_FREQUENCY_KEY: &str = "ingenialink.telemetry.achieved_frequency_hz";
/// Metadata key for recording markers.
const MARKERS_KEY: &str = "ingenialink.telemetry.markers";

/// Rust-owned Parquet recorder receiving decoded Rust-native telemetry samples.
pub struct TelemetryParquetRecorder {
    /// Parquet writer receiving Arrow record batches.
    writer: Option<ArrowWriter<File>>,
    /// Arrow schema used by the recording.
    schema: Arc<Schema>,
    /// Configured channel layout.
    channels: Vec<ChannelConfig>,
    /// Capacity used when recreating Arrow builders.
    batch_size: usize,
    /// Timestamp column builder.
    timestamp: Float64Builder,
    /// Firmware timestamp column builder.
    drive_timestamp: Float64Builder,
    /// Timestamp segment column builder.
    timestamp_segment: UInt64Builder,
    /// Typed channel column builders.
    channel_builders: Vec<Box<dyn ChannelAppender>>,
    /// Pending marker metadata.
    markers: Vec<serde_json::Value>,
    /// Latest decoded timestamp.
    last_timestamp: Option<f64>,
}

impl TelemetryParquetRecorder {
    /// Creates a Parquet recorder and writes the recording schema metadata.
    ///
    /// # Errors
    ///
    /// Returns an error when the schema, output file, or channel configuration
    /// cannot be created.
    pub fn new(
        path: impl AsRef<Path>,
        channels: Vec<ChannelConfig>,
        timestamp_frequency_hz: f64,
        requested_frequency_hz: f64,
        achieved_frequency_hz: f64,
        batch_size: usize,
    ) -> Result<Self, RecorderError> {
        if batch_size == 0 {
            return Err(RecorderError::InvalidConfiguration {
                field: "batch_size",
            });
        }
        let channel_builders = channels
            .iter()
            .enumerate()
            .map(|(index, channel)| new_channel_appender(channel, batch_size, index))
            .collect::<Result<Vec<_>, _>>()?;
        let mut fields = vec![
            Field::new("timestamp", ArrowDataType::Float64, false),
            Field::new("drive_timestamp", ArrowDataType::Float64, false),
            Field::new("timestamp_segment", ArrowDataType::UInt64, false),
            Field::new("host_time", ArrowDataType::Float64, true),
        ];
        for channel in &channels {
            fields.push(Field::new(
                &channel.identifier,
                channel_arrow_type(channel),
                true,
            ));
        }
        let mut metadata = std::collections::HashMap::new();
        metadata.insert(FORMAT_VERSION_KEY.to_string(), "2".to_string());
        metadata.insert(
            START_TIME_KEY.to_string(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map_err(|error| RecorderError::Parquet(error.to_string()))?
                .as_secs()
                .to_string(),
        );
        metadata.insert(
            TICK_FREQUENCY_KEY.to_string(),
            timestamp_frequency_hz.to_string(),
        );
        metadata.insert(
            REQUESTED_FREQUENCY_KEY.to_string(),
            requested_frequency_hz.to_string(),
        );
        metadata.insert(
            ACHIEVED_FREQUENCY_KEY.to_string(),
            achieved_frequency_hz.to_string(),
        );
        let schema = Arc::new(Schema::new_with_metadata(fields, metadata));
        let properties = WriterProperties::builder()
            .set_key_value_metadata(Some(
                schema
                    .metadata()
                    .iter()
                    .map(|(key, value)| KeyValue::new(key.clone(), value.clone()))
                    .collect(),
            ))
            .build();
        let file = File::create(path).map_err(|error| RecorderError::Parquet(error.to_string()))?;
        let writer = ArrowWriter::try_new(file, Arc::clone(&schema), Some(properties))
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        Ok(Self {
            writer: Some(writer),
            schema,
            channels,
            batch_size,
            timestamp: Float64Builder::with_capacity(batch_size),
            drive_timestamp: Float64Builder::with_capacity(batch_size),
            timestamp_segment: UInt64Builder::with_capacity(batch_size),
            channel_builders,
            markers: Vec::new(),
            last_timestamp: None,
        })
    }

    /// Finishes the current Arrow builders and writes one record batch.
    fn write_builders(&mut self) -> Result<(), RecorderError> {
        let mut columns: Vec<ArrayRef> = vec![
            Arc::new(
                std::mem::replace(
                    &mut self.timestamp,
                    Float64Builder::with_capacity(self.batch_size),
                )
                .finish(),
            ),
            Arc::new(
                std::mem::replace(
                    &mut self.drive_timestamp,
                    Float64Builder::with_capacity(self.batch_size),
                )
                .finish(),
            ),
            Arc::new(
                std::mem::replace(
                    &mut self.timestamp_segment,
                    UInt64Builder::with_capacity(self.batch_size),
                )
                .finish(),
            ),
        ];
        let channels = self
            .channel_builders
            .drain(..)
            .map(|mut builder| builder.finish())
            .collect::<Vec<_>>();
        self.channel_builders = self
            .channels
            .iter()
            .enumerate()
            .map(|(index, channel)| new_channel_appender(channel, self.batch_size, index))
            .collect::<Result<Vec<_>, _>>()?;
        let host_time = Float64Array::from(
            (0..columns[0].len())
                .map(|index| (index == 0).then(unix_time_seconds))
                .collect::<Vec<_>>(),
        );
        columns.insert(3, Arc::new(host_time));
        columns.extend(channels);
        let batch = RecordBatch::try_new(Arc::clone(&self.schema), columns)
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        self.writer
            .as_mut()
            .ok_or_else(|| RecorderError::Parquet("recorder is closed".to_string()))?
            .write(&batch)
            .map_err(|error| RecorderError::Parquet(error.to_string()))
    }
}

impl TelemetrySink for TelemetryParquetRecorder {
    /// Appends decoded samples to Arrow columns and writes one Parquet batch.
    fn write_samples(&mut self, samples: &[DecodedSample]) -> Result<(), RecorderError> {
        if samples.is_empty() {
            return Ok(());
        }
        for sample in samples {
            self.timestamp.append_value(sample.timestamp);
            self.drive_timestamp.append_value(sample.drive_timestamp);
            self.timestamp_segment
                .append_value(sample.timestamp_segment);
            for (index, value) in sample.values.iter().enumerate() {
                self.channel_builders[index]
                    .append_value(value)
                    .map_err(|error| match error {
                        RecorderError::ChannelTypeMismatch { .. } => {
                            RecorderError::ChannelTypeMismatch { channel: index }
                        }
                        error => error,
                    })?;
            }
        }
        self.last_timestamp = samples.last().map(|sample| sample.timestamp);
        self.write_builders()
    }

    /// Adds a marker to the recording metadata.
    fn add_marker(
        &mut self,
        label: &str,
        timestamp: Option<f64>,
        epoch: usize,
    ) -> Result<(), RecorderError> {
        if self.writer.is_none() {
            return Err(RecorderError::Parquet("recorder is not open".to_string()));
        }
        let time = timestamp.or(self.last_timestamp).ok_or_else(|| {
            RecorderError::Parquet("no samples recorded; pass an explicit timestamp".to_string())
        })?;
        let mut marker = serde_json::json!({"time": time, "label": label});
        if epoch != 0 {
            marker["connection_epoch"] = serde_json::json!(epoch);
        }
        self.markers.push(marker);
        Ok(())
    }

    /// Closes the Parquet file.
    fn close(&mut self) -> Result<(), RecorderError> {
        let mut writer = self
            .writer
            .take()
            .ok_or_else(|| RecorderError::Parquet("recorder is already closed".to_string()))?;
        if !self.markers.is_empty() {
            writer.append_key_value_metadata(KeyValue::new(
                MARKERS_KEY.to_string(),
                serde_json::to_string(&self.markers)
                    .map_err(|error| RecorderError::Parquet(error.to_string()))?,
            ));
        }
        writer
            .close()
            .map_err(|error| RecorderError::Parquet(error.to_string()))?;
        Ok(())
    }
}

/// Returns the current wall-clock time as Unix seconds.
fn unix_time_seconds() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0.0, |duration| duration.as_secs_f64())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::data_type::ByteOrder;
    use crate::telemetry::sample::DecodedValue;
    use crate::telemetry::sink::TelemetrySink;

    fn channel(data_type: crate::data_type_python::DataType) -> ChannelConfig {
        ChannelConfig {
            identifier: "test".to_string(),
            data_type,
            byte_order: ByteOrder::Little,
        }
    }

    #[test]
    fn writes_native_samples_to_parquet() -> Result<(), RecorderError> {
        let path = std::env::temp_dir().join(format!(
            "ingenialink-telemetry-test-{}.parquet",
            std::process::id()
        ));
        let mut recorder = TelemetryParquetRecorder::new(
            &path,
            vec![channel(crate::data_type_python::DataType::U16)],
            1_000_000.0,
            1_000.0,
            1_000.0,
            1,
        )?;
        recorder.write_samples(&[DecodedSample {
            timestamp: 0.001,
            drive_timestamp: 0.001,
            timestamp_segment: 0,
            values: vec![DecodedValue::U16(42)],
        }])?;
        recorder.add_marker("sample", None, 0)?;
        recorder.close()?;
        assert!(path.is_file());
        std::fs::remove_file(path).map_err(|error| RecorderError::Parquet(error.to_string()))?;
        Ok(())
    }
}

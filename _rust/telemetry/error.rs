//! Telemetry recording errors.

use thiserror::Error;

use crate::data_type::CodecError;

/// Errors returned while parsing or decoding a telemetry access.
#[derive(Debug, Error, PartialEq)]
pub enum RecorderError {
    /// The recorder configuration cannot represent valid samples.
    #[error("{field} must be positive and finite")]
    InvalidConfiguration {
        /// Configuration field that failed validation.
        field: &'static str,
    },
    /// The access response is shorter than its declared frame payload.
    #[error(
        "telemetry access declares {frame_count} frames ({expected} bytes), but contains {actual} bytes"
    )]
    TruncatedAccess {
        /// Number of frames declared by the response.
        frame_count: usize,
        /// Number of bytes required by the declaration.
        expected: usize,
        /// Number of bytes present in the response.
        actual: usize,
    },
    /// A register type has no fixed payload size for telemetry decoding.
    #[error("telemetry channel {channel} has no fixed payload size")]
    VariableChannel {
        /// Channel index that has the variable-sized type.
        channel: usize,
    },
    /// A decoded frame has a different payload size than configured.
    #[error("telemetry frame has {actual} payload bytes; expected {expected}")]
    InvalidSampleSize {
        /// Payload bytes found in the frame.
        actual: usize,
        /// Payload bytes required by configured channels.
        expected: usize,
    },
    /// The shared register codec rejected a channel payload.
    #[error("failed to decode telemetry channel {channel}: {source}")]
    Decode {
        /// Channel index being decoded.
        channel: usize,
        /// Codec failure.
        source: CodecError,
    },
    /// A sink received a value variant that does not match its channel schema.
    #[error("telemetry channel {channel} has an incompatible decoded value")]
    ChannelTypeMismatch {
        /// Channel index with the incompatible value.
        channel: usize,
    },
    /// The Parquet writer could not create or write the recording.
    #[error("Parquet recording failed: {0}")]
    Parquet(String),
}

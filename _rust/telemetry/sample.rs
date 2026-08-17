//! Rust-native telemetry samples exchanged between decoding and recording.

/// One decoded value from a configured telemetry channel.
#[derive(Debug, Clone, PartialEq)]
pub(super) enum DecodedValue {
    /// Unsigned 8-bit integer.
    U8(u8),
    /// Signed 8-bit integer.
    S8(i8),
    /// Unsigned 16-bit integer.
    U16(u16),
    /// Signed 16-bit integer.
    S16(i16),
    /// Unsigned 32-bit integer.
    U32(u32),
    /// Signed 32-bit integer.
    S32(i32),
    /// Unsigned 64-bit integer.
    U64(u64),
    /// Signed 64-bit integer.
    S64(i64),
    /// Single-precision floating-point value.
    Float(f32),
    /// Boolean value.
    Bool(bool),
    /// Fixed-size raw byte buffer.
    ByteArray512(Box<[u8; 512]>),
}

/// One decoded telemetry frame with normalized timestamps.
#[derive(Debug, Clone, PartialEq)]
pub(super) struct DecodedSample {
    /// Continuous timestamp in seconds.
    pub(super) timestamp: f64,
    /// Raw firmware timestamp converted to seconds.
    pub(super) drive_timestamp: f64,
    /// Timestamp segment, incremented after a firmware timestamp reset.
    pub(super) timestamp_segment: u64,
    /// Decoded values in configured channel order.
    pub(super) values: Vec<DecodedValue>,
}

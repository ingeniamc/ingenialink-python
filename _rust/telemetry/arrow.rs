//! Arrow-specific telemetry column construction.

use arrow_array::builder::{
    ArrayBuilder, BooleanBuilder, FixedSizeBinaryBuilder, Float32Builder, Int8Builder,
    Int16Builder, Int32Builder, Int64Builder, UInt8Builder, UInt16Builder, UInt32Builder,
    UInt64Builder,
};
use arrow_schema::DataType as ArrowDataType;

use super::channel::ChannelConfig;
use super::error::RecorderError;
use super::sample::DecodedValue;
use crate::data_type::{ByteArray512, CodecError, FixedDataType};
use crate::data_type_python::DataType;

/// Returns the Arrow type used to store decoded values for a channel.
pub(super) fn channel_arrow_type(channel: &ChannelConfig) -> ArrowDataType {
    match channel.data_type {
        DataType::U8 => ArrowDataType::UInt8,
        DataType::S8 => ArrowDataType::Int8,
        DataType::U16 => ArrowDataType::UInt16,
        DataType::S16 => ArrowDataType::Int16,
        DataType::U32 => ArrowDataType::UInt32,
        DataType::S32 => ArrowDataType::Int32,
        DataType::U64 => ArrowDataType::UInt64,
        DataType::S64 => ArrowDataType::Int64,
        DataType::Float => ArrowDataType::Float32,
        DataType::Bool => ArrowDataType::Boolean,
        DataType::ByteArray512 => ArrowDataType::FixedSizeBinary(512),
        DataType::Str => ArrowDataType::Utf8,
    }
}

/// Creates a typed Arrow column builder for a telemetry channel.
///
/// # Errors
///
/// Returns [`RecorderError::VariableChannel`] when the channel uses a
/// variable-sized data type.
pub(super) fn new_channel_appender(
    channel_config: &ChannelConfig,
    capacity: usize,
    channel: usize,
) -> Result<Box<dyn ChannelAppender>, RecorderError> {
    let builder: Box<dyn ChannelAppender> = match channel_config.data_type {
        DataType::U8 => Box::new(UInt8Builder::with_capacity(capacity)),
        DataType::S8 => Box::new(Int8Builder::with_capacity(capacity)),
        DataType::U16 => Box::new(UInt16Builder::with_capacity(capacity)),
        DataType::S16 => Box::new(Int16Builder::with_capacity(capacity)),
        DataType::U32 => Box::new(UInt32Builder::with_capacity(capacity)),
        DataType::S32 => Box::new(Int32Builder::with_capacity(capacity)),
        DataType::U64 => Box::new(UInt64Builder::with_capacity(capacity)),
        DataType::S64 => Box::new(Int64Builder::with_capacity(capacity)),
        DataType::Float => Box::new(Float32Builder::with_capacity(capacity)),
        DataType::Bool => Box::new(BooleanBuilder::with_capacity(capacity)),
        DataType::ByteArray512 => Box::new(FixedSizeBinaryBuilder::with_capacity(
            capacity,
            ByteArray512::WIDTH as i32,
        )),
        DataType::Str => return Err(RecorderError::VariableChannel { channel }),
    };
    Ok(builder)
}

/// Appends parsed channel values to a typed Arrow column builder.
pub(super) trait ChannelAppender: ArrayBuilder {
    /// Converts a Rust-native channel value and appends it.
    ///
    /// # Errors
    ///
    /// Returns [`RecorderError::ChannelTypeMismatch`] when the value variant
    /// does not match the configured channel data type.
    fn append_value(&mut self, value: &DecodedValue) -> Result<(), RecorderError>;
}

/// Implements [`ChannelAppender`] for an integer Arrow builder.
macro_rules! integer_appender {
    ($builder:ty, $variant:ident) => {
        impl ChannelAppender for $builder {
            fn append_value(&mut self, value: &DecodedValue) -> Result<(), RecorderError> {
                let DecodedValue::$variant(value) = value else {
                    return Err(RecorderError::ChannelTypeMismatch { channel: 0 });
                };
                self.append_value(*value);
                Ok(())
            }
        }
    };
}

integer_appender!(UInt8Builder, U8);
integer_appender!(Int8Builder, S8);
integer_appender!(UInt16Builder, U16);
integer_appender!(Int16Builder, S16);
integer_appender!(UInt32Builder, U32);
integer_appender!(Int32Builder, S32);
integer_appender!(UInt64Builder, U64);
integer_appender!(Int64Builder, S64);

impl ChannelAppender for Float32Builder {
    fn append_value(&mut self, value: &DecodedValue) -> Result<(), RecorderError> {
        let DecodedValue::Float(value) = value else {
            return Err(RecorderError::ChannelTypeMismatch { channel: 0 });
        };
        self.append_value(*value);
        Ok(())
    }
}

impl ChannelAppender for BooleanBuilder {
    fn append_value(&mut self, value: &DecodedValue) -> Result<(), RecorderError> {
        let DecodedValue::Bool(value) = value else {
            return Err(RecorderError::ChannelTypeMismatch { channel: 0 });
        };
        self.append_value(*value);
        Ok(())
    }
}

impl ChannelAppender for FixedSizeBinaryBuilder {
    fn append_value(&mut self, value: &DecodedValue) -> Result<(), RecorderError> {
        let DecodedValue::ByteArray512(value) = value else {
            return Err(RecorderError::ChannelTypeMismatch { channel: 0 });
        };
        self.append_value(value.as_slice())
            .map_err(|_| RecorderError::Decode {
                channel: 0,
                source: CodecError::InvalidBufferLength {
                    expected: ByteArray512::WIDTH,
                    got: value.len(),
                },
            })?;
        Ok(())
    }
}

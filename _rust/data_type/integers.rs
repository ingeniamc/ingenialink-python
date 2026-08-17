//! Fixed-width integer register data types for Rust callers.

use super::{CodecError, FixedDataType, exact_bytes};

/// Define a fixed-width integer data type and its parsers.
macro_rules! define_integer_type {
    ($name:ident, $primitive:ty, $width:literal, $signed:literal) => {
        /// Fixed-width register data type.
        pub struct $name;

        impl $name {
            /// Parse an exact-width little-endian byte array.
            pub fn from_le_bytes(bytes: [u8; $width]) -> $primitive {
                <$primitive>::from_le_bytes(bytes)
            }

            /// Parse an exact-width big-endian byte array.
            pub fn from_be_bytes(bytes: [u8; $width]) -> $primitive {
                <$primitive>::from_be_bytes(bytes)
            }

            /// Parse a little-endian payload after validating its length.
            ///
            /// # Errors
            ///
            /// Returns [`CodecError::InvalidBufferLength`] when the payload
            /// width is not `$width`.
            pub fn parse(data: impl AsRef<[u8]>) -> Result<$primitive, CodecError> {
                <Self as FixedDataType>::parse(data)
            }

            /// Parse a big-endian payload after validating its length.
            ///
            /// # Errors
            ///
            /// Returns [`CodecError::InvalidBufferLength`] when the payload
            /// width is not `$width`.
            pub fn parse_be(data: impl AsRef<[u8]>) -> Result<$primitive, CodecError> {
                <Self as FixedDataType>::parse_be(data)
            }

            /// Encodes a value in little-endian byte order.
            pub fn encode(value: $primitive) -> Vec<u8> {
                <$primitive>::to_le_bytes(value).to_vec()
            }

            /// Encodes a value in big-endian byte order.
            pub fn encode_be(value: $primitive) -> Vec<u8> {
                <$primitive>::to_be_bytes(value).to_vec()
            }
        }

        impl FixedDataType for $name {
            type Value = $primitive;

            const WIDTH: usize = $width;

            const SIGNED: bool = $signed;

            fn parse(data: impl AsRef<[u8]>) -> Result<Self::Value, CodecError> {
                Ok(Self::from_le_bytes(exact_bytes::<$width>(data)?))
            }

            fn parse_be(data: impl AsRef<[u8]>) -> Result<Self::Value, CodecError> {
                Ok(Self::from_be_bytes(exact_bytes::<$width>(data)?))
            }

            fn encode(value: Self::Value) -> Vec<u8> {
                Self::encode(value)
            }

            fn encode_be(value: Self::Value) -> Vec<u8> {
                Self::encode_be(value)
            }
        }
    };
}

define_integer_type!(U8, u8, 1, false);
define_integer_type!(S8, i8, 1, true);
define_integer_type!(U16, u16, 2, false);
define_integer_type!(S16, i16, 2, true);
define_integer_type!(U32, u32, 4, false);
define_integer_type!(S32, i32, 4, true);
define_integer_type!(U64, u64, 8, false);
define_integer_type!(S64, i64, 8, true);

#[cfg(test)]
#[allow(clippy::unwrap_used)]
mod tests {
    use super::{FixedDataType, U16, U64};
    use crate::data_type::CodecError;

    #[test]
    fn typed_parsers_use_native_endianness() {
        assert_eq!(U16::from_le_bytes([0x34, 0x12]), 0x1234);
        assert_eq!(U64::from_be_bytes([0, 0, 0, 0, 0, 0, 0, 1]), 1);
        assert_eq!(U16::encode(0x1234), [0x34, 0x12]);
        assert_eq!(U16::encode_be(0x1234), [0x12, 0x34]);
    }

    #[test]
    fn dynamic_parsers_validate_width() {
        assert_eq!(
            U64::parse([1, 2, 3]).unwrap_err(),
            CodecError::InvalidBufferLength {
                expected: 8,
                got: 3,
            }
        );
        assert_eq!(U16::parse_be([0x12, 0x34]).unwrap(), 0x1234);
        assert_eq!(<U64 as FixedDataType>::WIDTH, 8);
    }
}

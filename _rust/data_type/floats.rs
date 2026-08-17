//! Fixed-width floating-point register data types.

use super::{CodecError, FixedDataType, exact_bytes};

/// Fixed-width IEEE 754 single-precision register data type.
pub struct F32;

impl F32 {
    /// Parse an exact-width little-endian byte array.
    pub fn from_le_bytes(bytes: [u8; 4]) -> f32 {
        f32::from_le_bytes(bytes)
    }

    /// Parse an exact-width big-endian byte array.
    pub fn from_be_bytes(bytes: [u8; 4]) -> f32 {
        f32::from_be_bytes(bytes)
    }

    /// Parse a little-endian payload after validating its length.
    ///
    /// # Errors
    ///
    /// Returns [`CodecError::InvalidBufferLength`] when the payload is not
    /// four bytes wide.
    pub fn parse(data: impl AsRef<[u8]>) -> Result<f32, CodecError> {
        <Self as FixedDataType>::parse(data)
    }

    /// Parse a big-endian payload after validating its length.
    ///
    /// # Errors
    ///
    /// Returns [`CodecError::InvalidBufferLength`] when the payload is not
    /// four bytes wide.
    pub fn parse_be(data: impl AsRef<[u8]>) -> Result<f32, CodecError> {
        <Self as FixedDataType>::parse_be(data)
    }

    /// Encodes a value in little-endian byte order.
    pub fn encode(value: f32) -> Vec<u8> {
        value.to_le_bytes().to_vec()
    }

    /// Encodes a value in big-endian byte order.
    pub fn encode_be(value: f32) -> Vec<u8> {
        value.to_be_bytes().to_vec()
    }
}

impl FixedDataType for F32 {
    type Value = f32;

    const WIDTH: usize = 4;

    const SIGNED: bool = false;

    fn parse(data: impl AsRef<[u8]>) -> Result<Self::Value, CodecError> {
        Ok(Self::from_le_bytes(exact_bytes::<4>(data)?))
    }

    fn parse_be(data: impl AsRef<[u8]>) -> Result<Self::Value, CodecError> {
        Ok(Self::from_be_bytes(exact_bytes::<4>(data)?))
    }

    fn encode(value: Self::Value) -> Vec<u8> {
        Self::encode(value)
    }

    fn encode_be(value: Self::Value) -> Vec<u8> {
        Self::encode_be(value)
    }
}

#[cfg(test)]
mod tests {
    use super::F32;

    #[test]
    fn encodes_both_byte_orders() {
        assert_eq!(F32::encode(34.5), [0x00, 0x00, 0x0A, 0x42]);
        assert_eq!(F32::encode_be(34.5), [0x42, 0x0A, 0x00, 0x00]);
    }
}

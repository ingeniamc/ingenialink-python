//! Fixed-width raw byte-array register support.

use super::{CodecError, FixedDataType, exact_bytes};

/// Fixed-width 512-byte register data type.
pub struct ByteArray512;

impl ByteArray512 {
    /// Returns an exact-width byte array without runtime parsing.
    pub fn from_bytes(bytes: [u8; 512]) -> [u8; 512] {
        bytes
    }

    /// Parses a 512-byte payload after validating its length.
    ///
    /// # Errors
    ///
    /// Returns [`CodecError::InvalidBufferLength`] unless the payload has
    /// exactly 512 bytes.
    pub fn parse(data: impl AsRef<[u8]>) -> Result<[u8; 512], CodecError> {
        <Self as FixedDataType>::parse(data)
    }

    /// Returns an exact-width byte array as a byte vector.
    pub fn encode(value: [u8; 512]) -> Vec<u8> {
        value.to_vec()
    }
}

impl FixedDataType for ByteArray512 {
    type Value = [u8; 512];

    const WIDTH: usize = 512;

    const SIGNED: bool = false;

    fn parse(data: impl AsRef<[u8]>) -> Result<Self::Value, CodecError> {
        exact_bytes::<512>(data)
    }

    fn parse_be(data: impl AsRef<[u8]>) -> Result<Self::Value, CodecError> {
        Self::parse(data)
    }

    fn encode(value: Self::Value) -> Vec<u8> {
        Self::encode(value)
    }

    fn encode_be(value: Self::Value) -> Vec<u8> {
        Self::encode(value)
    }
}

#[cfg(test)]
mod tests {
    use super::ByteArray512;
    use crate::data_type::{CodecError, FixedDataType};

    #[test]
    fn enforces_and_encodes_exact_width() {
        let value = ByteArray512::from_bytes([0xA5; 512]);
        assert_eq!(ByteArray512::encode(value), vec![0xA5; 512]);
        assert_eq!(
            ByteArray512::parse([0; 511]),
            Err(CodecError::InvalidBufferLength {
                expected: 512,
                got: 511,
            })
        );
        assert_eq!(<ByteArray512 as FixedDataType>::WIDTH, 512);
    }
}

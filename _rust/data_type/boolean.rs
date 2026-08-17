//! Fixed-width boolean register data type.

use super::{CodecError, FixedDataType, exact_bytes};

/// Fixed-width boolean register data type.
pub struct Bool;

impl Bool {
    /// Parse an exact-width boolean byte array.
    pub fn from_bytes(bytes: [u8; 1]) -> bool {
        bytes[0] != 0
    }

    /// Parse a boolean payload after validating its length.
    ///
    /// # Errors
    ///
    /// Returns [`CodecError::InvalidBufferLength`] when the payload is not
    /// one byte wide.
    pub fn parse(data: impl AsRef<[u8]>) -> Result<bool, CodecError> {
        <Self as FixedDataType>::parse(data)
    }

    /// Encodes a boolean as one byte.
    pub fn encode(value: bool) -> Vec<u8> {
        vec![u8::from(value)]
    }
}

impl FixedDataType for Bool {
    type Value = bool;

    const WIDTH: usize = 1;

    const SIGNED: bool = false;

    fn parse(data: impl AsRef<[u8]>) -> Result<Self::Value, CodecError> {
        Ok(Self::from_bytes(exact_bytes::<1>(data)?))
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
    use super::Bool;

    #[test]
    fn encodes_true_and_false() {
        assert_eq!(Bool::encode(true), [1]);
        assert_eq!(Bool::encode(false), [0]);
    }
}

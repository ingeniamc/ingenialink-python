//! Variable-length UTF-8 register string support.

use super::CodecError;

/// Decode a NUL-terminated UTF-8 payload.
pub(crate) fn decode(data: &[u8]) -> Result<String, CodecError> {
    let text = data.split(|byte| *byte == 0).next().unwrap_or(data);
    let value = std::str::from_utf8(text).map_err(|_| CodecError::InvalidUtf8)?;
    Ok(value.to_owned())
}

/// Encodes a UTF-8 register string.
pub(crate) fn encode(value: &str) -> Vec<u8> {
    value.as_bytes().to_vec()
}

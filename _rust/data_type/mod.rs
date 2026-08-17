//! Fixed-width register data types and their native Rust parsers.
//!
//! Runtime dispatch belongs to the Python adapter. This module deliberately
//! exposes concrete types such as [`U64`] and [`F32`] for Rust consumers.

use thiserror::Error;

mod boolean;
pub(crate) mod byte_array;
mod floats;
mod integers;
pub(crate) mod string;

pub use boolean::Bool;
pub use byte_array::ByteArray512;
pub use floats::F32;
pub use integers::{S8, S16, S32, S64, U8, U16, U32, U64};

/// Common interface for fixed-width register data types.
pub trait FixedDataType {
    /// Native Rust value produced by this data type.
    type Value;

    /// Number of bytes required by this data type.
    const WIDTH: usize;

    /// Whether this data type represents a signed integer.
    const SIGNED: bool;

    /// Parses a little-endian payload after validating its length.
    ///
    /// # Errors
    ///
    /// Returns [`CodecError::InvalidBufferLength`] when the payload width is
    /// not [`Self::WIDTH`].
    fn parse(data: impl AsRef<[u8]>) -> Result<Self::Value, CodecError>;

    /// Parses a big-endian payload after validating its length.
    ///
    /// # Errors
    ///
    /// Returns [`CodecError::InvalidBufferLength`] when the payload width is
    /// not [`Self::WIDTH`].
    fn parse_be(data: impl AsRef<[u8]>) -> Result<Self::Value, CodecError>;

    /// Encodes a value in little-endian byte order.
    fn encode(value: Self::Value) -> Vec<u8>;

    /// Encodes a value in big-endian byte order.
    fn encode_be(value: Self::Value) -> Vec<u8>;
}

/// Converts a dynamically sized payload to a fixed-size byte array.
fn exact_bytes<const N: usize>(data: impl AsRef<[u8]>) -> Result<[u8; N], CodecError> {
    let data = data.as_ref();
    data.try_into()
        .map_err(|_| CodecError::InvalidBufferLength {
            expected: N,
            got: data.len(),
        })
}

/// Byte order selected by a dynamic caller.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ByteOrder {
    /// Least-significant byte first.
    Little,
    /// Most-significant byte first.
    Big,
}

impl ByteOrder {
    /// Parses a byte order from its Python-side string representation.
    pub fn parse(value: &str) -> Option<Self> {
        match value {
            "little" => Some(Self::Little),
            "big" => Some(Self::Big),
            _ => None,
        }
    }
}

/// Errors produced by native data-type parsers.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum CodecError {
    /// The payload length does not match the fixed-size data type.
    #[error("payload has {got} bytes, expected {expected} bytes")]
    InvalidBufferLength {
        /// Required payload length in bytes.
        expected: usize,
        /// Actual payload length in bytes.
        got: usize,
    },
    /// A string payload is not valid UTF-8.
    #[error("string payload is not valid utf-8")]
    InvalidUtf8,
}

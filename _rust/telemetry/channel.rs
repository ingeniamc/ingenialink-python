//! Telemetry channel configuration and payload layout.

use crate::data_type::ByteOrder;
use crate::data_type_python::DataType;

/// One register mapped into a telemetry channel.
///
/// The configuration is snapshotted by the Python boundary once per recorder
/// or decoder construction, so the decode core never touches Python objects.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct ChannelConfig {
    /// Register identifier used in the output schema.
    pub identifier: String,
    /// Register data type.
    pub data_type: DataType,
    /// Byte order used by the register payload.
    pub byte_order: ByteOrder,
}

impl ChannelConfig {
    /// Creates a telemetry channel configuration from its identifying fields.
    pub(super) fn new(identifier: String, data_type: DataType) -> Self {
        Self {
            identifier,
            data_type,
            byte_order: ByteOrder::Little,
        }
    }

    /// Returns the fixed payload width of the channel, `None` when variable.
    pub(super) fn byte_length(&self) -> Option<usize> {
        self.data_type.byte_length()
    }
}

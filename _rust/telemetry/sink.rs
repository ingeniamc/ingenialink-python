//! Sinks for decoded telemetry samples.

use super::error::RecorderError;
use super::sample::DecodedSample;

/// Receives decoded telemetry samples and owns an output representation.
pub(super) trait TelemetrySink: Send {
    /// Converts and writes a decoded sample batch.
    fn write_samples(&mut self, samples: &[DecodedSample]) -> Result<(), RecorderError>;

    /// Adds a marker to the output metadata.
    fn add_marker(
        &mut self,
        label: &str,
        timestamp: Option<f64>,
        epoch: usize,
    ) -> Result<(), RecorderError>;

    /// Closes the output.
    fn close(&mut self) -> Result<(), RecorderError>;
}

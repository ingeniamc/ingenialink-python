//! Rust implementations shared by the ingenialink Python package.
//!
//! The crate builds the `ingenialink._rust` extension module, whose
//! declarative submodules expose the Python-facing data-type API.

pub mod data_type;
mod data_type_python;
pub mod telemetry;

use pyo3::prelude::*;

/// The `ingenialink._rust` extension module.
///
/// Declarative [`pymodule`] submodules are mounted as plain module attributes,
/// so Python code reaches them as `from ingenialink._rust import data_type` rather
/// than through a file-backed submodule package.
#[pymodule]
#[pyo3(module = "ingenialink")]
mod _rust {
    use pyo3::prelude::*;

    /// The `data_type` submodule, exposing the dynamic Python data-type API.
    #[pymodule]
    mod data_type {
        #[pymodule_export]
        use crate::data_type_python::ConfiguredDataType;
        #[pymodule_export]
        use crate::data_type_python::DataType;
    }

    /// The `telemetry` submodule, exposing the Rust recorder decode core.
    #[pymodule]
    mod telemetry {
        #[pymodule_export]
        use crate::telemetry::PyTelemetryArrowIpcSink as TelemetryArrowIpcSink;
        #[pymodule_export]
        use crate::telemetry::PyTelemetryDecoder as TelemetryDecoder;
        #[pymodule_export]
        use crate::telemetry::PyTelemetryParquetRecorder as TelemetryParquetRecorder;
    }
}

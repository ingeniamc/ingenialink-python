//! Python bindings and runtime dispatch for the native register data types.

use pyo3::IntoPyObjectExt;
use pyo3::exceptions::{PyOverflowError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBool, PyBytes, PyBytesMethods, PyString, PyStringMethods, PyType};

use crate::data_type::{self, Bool, ByteArray512, ByteOrder, CodecError, F32, FixedDataType};
use crate::data_type::{S8, S16, S32, S64, U8, U16, U32, U64};

pyo3::import_exception!(ingenialink.exceptions, ILValueError);

/// Runtime data-type identifier used by Python callers.
#[pyclass(eq, skip_from_py_object)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum DataType {
    /// Unsigned 8-bit integer.
    U8,
    /// Signed 8-bit integer.
    S8,
    /// Unsigned 16-bit integer.
    U16,
    /// Signed 16-bit integer.
    S16,
    /// Unsigned 32-bit integer.
    U32,
    /// Signed 32-bit integer.
    S32,
    /// Unsigned 64-bit integer.
    U64,
    /// Signed 64-bit integer.
    S64,
    /// IEEE 754 single-precision float.
    Float,
    /// UTF-8 string.
    Str,
    /// Raw byte buffer.
    ByteArray512,
    /// Boolean value.
    Bool,
}

/// A register data type with its byte order fixed for repeated Python calls.
#[pyclass(frozen, skip_from_py_object)]
#[derive(Debug, Clone, Copy)]
pub struct ConfiguredDataType {
    /// Native register data type.
    data_type: DataType,
    /// Byte order used by conversions.
    byte_order: ByteOrder,
}

#[pymethods]
impl DataType {
    /// Resolves a data type from its symbolic Python enum name.
    #[staticmethod]
    pub fn from_name(value: &str) -> Option<Self> {
        let data_type = match value {
            "U8" => Self::U8,
            "S8" => Self::S8,
            "U16" => Self::U16,
            "S16" => Self::S16,
            "U32" => Self::U32,
            "S32" => Self::S32,
            "U64" => Self::U64,
            "S64" => Self::S64,
            "FLOAT" => Self::Float,
            "STR" => Self::Str,
            "BYTE_ARRAY_512" => Self::ByteArray512,
            "BOOL" => Self::Bool,
            _ => return None,
        };
        Some(data_type)
    }

    /// Fixes the byte order for repeated conversions.
    fn with_byte_order(&self, byte_order: &str) -> PyResult<ConfiguredDataType> {
        Ok(ConfiguredDataType {
            data_type: *self,
            byte_order: byte_order_from_py(byte_order)?,
        })
    }

    /// Returns the fixed byte length of the data type, `None` when variable.
    pub fn byte_length(&self) -> Option<usize> {
        match *self {
            Self::U8 => Some(U8::WIDTH),
            Self::S8 => Some(S8::WIDTH),
            Self::U16 => Some(U16::WIDTH),
            Self::S16 => Some(S16::WIDTH),
            Self::U32 => Some(U32::WIDTH),
            Self::S32 => Some(S32::WIDTH),
            Self::U64 => Some(U64::WIDTH),
            Self::S64 => Some(S64::WIDTH),
            Self::Float => Some(F32::WIDTH),
            Self::Bool => Some(Bool::WIDTH),
            Self::ByteArray512 => Some(ByteArray512::WIDTH),
            Self::Str => None,
        }
    }

    /// Returns the bit length of the data type, `None` when variable.
    fn bit_length(&self) -> Option<usize> {
        self.byte_length().map(|length| length * 8)
    }

    /// Returns whether the data type decodes as a two's complement integer.
    fn is_signed(&self) -> bool {
        match *self {
            Self::U8 => U8::SIGNED,
            Self::S8 => S8::SIGNED,
            Self::U16 => U16::SIGNED,
            Self::S16 => S16::SIGNED,
            Self::U32 => U32::SIGNED,
            Self::S32 => S32::SIGNED,
            Self::U64 => U64::SIGNED,
            Self::S64 => S64::SIGNED,
            Self::Float => F32::SIGNED,
            Self::Bool => Bool::SIGNED,
            Self::ByteArray512 => ByteArray512::SIGNED,
            Self::Str => false,
        }
    }
}

#[pymethods]
impl ConfiguredDataType {
    /// Deserializes a payload using the configured byte order.
    #[pyo3(signature = (data: "bytes") -> "int | float | str | bytes")]
    fn bytes_to_value(&self, py: Python<'_>, data: &Bound<'_, PyBytes>) -> PyResult<Py<PyAny>> {
        self.data_type.decode(py, data, self.byte_order)
    }

    /// Serializes a Python value using the configured byte order.
    #[pyo3(signature = (value: "int | float | str | bytes") -> "bytes")]
    fn value_to_bytes(&self, py: Python<'_>, value: &Bound<'_, PyAny>) -> PyResult<Py<PyAny>> {
        self.data_type.encode(py, value, self.byte_order)
    }

    /// Returns the fixed byte length of the configured data type, `None` when variable.
    fn byte_length(&self) -> Option<usize> {
        self.data_type.byte_length()
    }

    /// Returns the bit length of the configured data type, `None` when variable.
    fn bit_length(&self) -> Option<usize> {
        self.data_type.bit_length()
    }

    /// Returns whether the configured data type decodes as a signed integer.
    fn is_signed(&self) -> bool {
        self.data_type.is_signed()
    }
}

impl DataType {
    /// Decodes a payload using the selected byte order.
    fn decode(
        self,
        py: Python<'_>,
        data: &Bound<'_, PyBytes>,
        byte_order: ByteOrder,
    ) -> PyResult<Py<PyAny>> {
        let payload = data.as_bytes();
        match self {
            Self::Float => f64::from(parse::<F32>(payload, byte_order)?).into_py_any(py),
            Self::Bool => parse::<Bool>(payload, byte_order)?.into_py_any(py),
            Self::Str => data_type::string::decode(payload)?.into_py_any(py),
            Self::ByteArray512 => {
                ByteArray512::parse(payload)?;
                data.clone().into_any().unbind().into_py_any(py)
            }
            Self::U8 => decode_integer::<U8>(payload, byte_order)?.into_py_any(py),
            Self::S8 => decode_integer::<S8>(payload, byte_order)?.into_py_any(py),
            Self::U16 => decode_integer::<U16>(payload, byte_order)?.into_py_any(py),
            Self::S16 => decode_integer::<S16>(payload, byte_order)?.into_py_any(py),
            Self::U32 => decode_integer::<U32>(payload, byte_order)?.into_py_any(py),
            Self::S32 => decode_integer::<S32>(payload, byte_order)?.into_py_any(py),
            Self::U64 => decode_integer::<U64>(payload, byte_order)?.into_py_any(py),
            Self::S64 => decode_integer::<S64>(payload, byte_order)?.into_py_any(py),
        }
    }

    /// Encodes a Python value using the selected byte order.
    fn encode(
        self,
        py: Python<'_>,
        value: &Bound<'_, PyAny>,
        byte_order: ByteOrder,
    ) -> PyResult<Py<PyAny>> {
        match self {
            Self::ByteArray512 => {
                let bytes = value
                    .cast::<PyBytes>()
                    .map_err(|_| type_error(value, "bytes"))?;
                ByteArray512::parse(bytes.as_bytes())?;
                Ok(bytes.clone().into_any().unbind())
            }
            Self::Str => {
                let text = value
                    .cast::<PyString>()
                    .map_err(|_| type_error(value, "string"))?;
                let bytes = data_type::string::encode(text.to_cow()?.as_ref());
                Ok(PyBytes::new(py, &bytes).into_any().unbind())
            }
            Self::Float => encode_fixed::<F32>(py, float_from_py(value)? as f32, byte_order),
            Self::Bool => encode_fixed::<Bool>(py, bool_from_py(value)?, byte_order),
            Self::U8 => encode_integer::<U8>(py, value, byte_order),
            Self::S8 => encode_integer::<S8>(py, value, byte_order),
            Self::U16 => encode_integer::<U16>(py, value, byte_order),
            Self::S16 => encode_integer::<S16>(py, value, byte_order),
            Self::U32 => encode_integer::<U32>(py, value, byte_order),
            Self::S32 => encode_integer::<S32>(py, value, byte_order),
            Self::U64 => encode_integer::<U64>(py, value, byte_order),
            Self::S64 => encode_integer::<S64>(py, value, byte_order),
        }
    }
}

/// Parses an integer using the selected byte order.
fn decode_integer<T>(data: &[u8], byte_order: ByteOrder) -> Result<T::Value, CodecError>
where
    T: FixedDataType,
{
    parse::<T>(data, byte_order)
}

/// Parses a fixed-width native data type with the requested byte order.
fn parse<T: FixedDataType>(data: &[u8], byte_order: ByteOrder) -> Result<T::Value, CodecError> {
    match byte_order {
        ByteOrder::Little => T::parse(data),
        ByteOrder::Big => T::parse_be(data),
    }
}

/// Encodes a fixed-width value with the requested byte order.
fn encode_fixed<T: FixedDataType>(
    py: Python<'_>,
    value: T::Value,
    byte_order: ByteOrder,
) -> PyResult<Py<PyAny>> {
    let bytes = match byte_order {
        ByteOrder::Little => T::encode(value),
        ByteOrder::Big => T::encode_be(value),
    };
    Ok(PyBytes::new(py, &bytes).into_any().unbind())
}

/// Converts a Python integer to a fixed-width native value and encodes it.
fn encode_integer<T>(
    py: Python<'_>,
    value: &Bound<'_, PyAny>,
    byte_order: ByteOrder,
) -> PyResult<Py<PyAny>>
where
    T: FixedDataType,
    T::Value: TryFrom<i128>,
{
    let number = value
        .extract::<i128>()
        .map_err(|_| type_error(value, "int"))?;
    let typed = T::Value::try_from(number)
        .map_err(|_| PyOverflowError::new_err(format!("value {number} is out of range")))?;
    encode_fixed::<T>(py, typed, byte_order)
}

/// Converts a Python value to a boolean using the package's validation rules.
fn bool_from_py(value: &Bound<'_, PyAny>) -> PyResult<bool> {
    if value.is_instance_of::<PyBool>() {
        value.is_truthy()
    } else if let Ok(number) = value.extract::<i64>() {
        match number {
            0 => Ok(false),
            1 => Ok(true),
            _ => Err(boolean_value_error(value)),
        }
    } else {
        Err(boolean_value_error(value))
    }
}

/// Converts a Python value to a floating-point value using Python coercion.
fn float_from_py(value: &Bound<'_, PyAny>) -> PyResult<f64> {
    if value.is_instance_of::<PyBool>() {
        Ok(if value.is_truthy()? { 1.0 } else { 0.0 })
    } else {
        value
            .extract::<f64>()
            .map_err(|_| type_error(value, "float"))
    }
}

/// Converts native parser errors into Python exceptions.
impl From<CodecError> for PyErr {
    fn from(error: CodecError) -> Self {
        match error {
            CodecError::InvalidBufferLength { expected, .. } => Python::attach(|py| {
                let message = format!("unpack requires a buffer of {expected} bytes");
                let fallback = PyValueError::new_err(message.clone());
                let Ok(module) = py.import("struct") else {
                    return fallback;
                };
                let Ok(exception_type) = module.getattr("error") else {
                    return fallback;
                };
                let Ok(exception_type) = exception_type.cast_into::<PyType>() else {
                    return fallback;
                };
                PyErr::from_type(exception_type, message)
            }),
            CodecError::InvalidUtf8 => {
                ILValueError::new_err("Can't decode payload to utf-8 string")
            }
        }
    }
}

/// Resolves the byte order from its Python string representation.
fn byte_order_from_py(value: &str) -> PyResult<ByteOrder> {
    ByteOrder::parse(value)
        .ok_or_else(|| PyValueError::new_err(format!("unsupported byte order {value}")))
}

/// Builds the boolean validation error raised by the Python implementation.
fn boolean_value_error(value: &Bound<'_, PyAny>) -> PyErr {
    let repr = value
        .str()
        .map(|text| text.to_string())
        .unwrap_or_else(|_| "?".to_owned());
    PyValueError::new_err(format!(
        "Invalid value. Expected values: [0, 1, True, False], got {repr}"
    ))
}

/// Builds a type error for a Python value.
fn type_error(value: &Bound<'_, PyAny>, expected: &str) -> PyErr {
    let actual = value
        .get_type()
        .str()
        .map(|name| name.to_string())
        .unwrap_or_else(|_| "unknown type".to_owned());
    PyValueError::new_err(format!(
        "Expected data of type {expected}, but got {actual}"
    ))
}

"""EtherCAT telemetry service descriptor."""

from ingenialink.telemetry import TelemetryDescriptor

ETHERCAT_TELEMETRY = TelemetryDescriptor(
    name="EtherCAT",
    max_channels=16,
    data_buffer_size=8 * 1024,  # 8 KiB. TODO: New data type ByteArray 8192
    base_frequency_hz=1_000_000,
    max_frequency_divider=0xFFFF,
    timestamp_size=8,
    timestamp_frequency_hz=1_000_000,
    frame_count_size=2,
    status_reg_uid="TEL_STATUS",
    data_reg_uid="TEL_DATA_VALUE",
    sample_size_reg_uid="TEL_CFG_BYTES_VALUE",
    enable_reg_uid="TEL_ENABLE",
    frequency_divider_reg_uid="TEL_FREQ_DIV",
    adaptive_rate_reg_uid="TEL_ADAPTIVE_RATE",
    mapped_register_count_reg_uid="TEL_CFG_TOTAL_MAP",
    mapped_register_prefix="TEL_CFG_REG",
)

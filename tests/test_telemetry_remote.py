import json
import socket
from pathlib import Path

import pyarrow as pa

from ingenialink.telemetry_remote import TelemetryRemoteSession


def _request(address: str, payload: dict[str, object]) -> dict[str, object]:
    """Send one control request and read its response.

    Returns:
        Decoded control response.
    """
    host, port = address.rsplit(":", 1)
    with socket.create_connection((host, int(port)), timeout=2) as connection:
        connection.sendall(json.dumps(payload).encode() + b"\n")
        return json.loads(connection.makefile("rb").readline())


def test_remote_session_streams_real_arrow_batches(
    virtual_drive_ethercat_telemetry, tmp_path: Path
) -> None:
    """Verify control commands and Arrow IPC batches against a virtual drive."""
    _, _, servo = virtual_drive_ethercat_telemetry
    counter = servo.dictionary.get_register("DRV_DIAG_ERROR_LAST_COM", axis=0)
    remote = TelemetryRemoteSession(
        servo,
        [counter],
        str(tmp_path / "telemetry.parquet"),
        batch_size=10,
        frequency=2_000,
    )
    remote.start()
    data_socket: socket.socket | None = None
    try:
        configured = _request(
            remote.control_endpoint.as_text(),
            {
                "id": "configure",
                "command": "configure",
                "registers": [counter.identifier],
                "frequency_hz": 2_000,
            },
        )
        assert configured["ok"] is True
        assert configured["state"] == "configured"

        started = _request(remote.control_endpoint.as_text(), {"id": "start", "command": "start"})
        assert started["state"] == "running"
        data_address = started["data_address"]
        assert isinstance(data_address, str)

        data_host, data_port = data_address.rsplit(":", 1)
        data_socket = socket.create_connection((data_host, int(data_port)), timeout=2)
        reader = pa.ipc.open_stream(data_socket.makefile("rb"))
        batch = next(reader)

        assert batch.num_rows >= 1
        assert batch.column_names == [
            "timestamp",
            "drive_timestamp",
            "timestamp_segment",
            "host_time",
            counter.identifier,
        ]
        assert all(value == 0 for value in batch.column(counter.identifier).to_pylist())

        paused = _request(remote.control_endpoint.as_text(), {"command": "pause"})
        assert paused["state"] == "paused"
    finally:
        if data_socket is not None:
            data_socket.close()
        remote.stop()

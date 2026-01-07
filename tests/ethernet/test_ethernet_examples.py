from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from summit_testing_framework.setup_fixtures import ConnectionWrapper


@pytest.fixture
def arguments(setup_descriptor):
    attrs = [
        f"--dictionary_path={setup_descriptor.dictionary}",
        f"--ip_address={setup_descriptor.ip}",
        f"--port={setup_descriptor.port}",
    ]
    yield attrs


@pytest.mark.ethernet
def test_connection_example(
    arguments, script_runner, servo_with_reconnect_force_restore: "ConnectionWrapper"
) -> None:
    servo_with_reconnect_force_restore.disconnect()

    script_path = "examples/ethernet/eth_connection.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"


@pytest.mark.ethernet
def test_load_firmware_example(
    arguments, script_runner, mocker, servo_with_reconnect_force_restore: "ConnectionWrapper"
) -> None:
    servo_with_reconnect_force_restore.disconnect()

    mock = mocker.patch("ingenialink.ethernet.network.EthernetNetwork.load_firmware")
    script_path = "examples/ethernet/eth_load_firmware.py"
    result = script_runner.run([script_path, "--firmware_path=./dummy.sfu", arguments[1]])
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"
    mock.assert_called_once()


@pytest.mark.ethernet
def test_load_save_config_example(
    arguments, script_runner, servo_with_reconnect_force_restore: "ConnectionWrapper"
) -> None:
    servo_with_reconnect_force_restore.disconnect()

    script_path = "examples/ethernet/eth_load_save_config.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"


@pytest.mark.ethernet
def test_monitoring_example(
    arguments, script_runner, servo_with_reconnect_force_restore: "ConnectionWrapper"
) -> None:
    servo_with_reconnect_force_restore.disconnect()

    script_path = "examples/ethernet/eth_monitoring.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"


@pytest.mark.ethernet
def test_store_restore_example(
    arguments, script_runner, servo_with_reconnect_force_restore: "ConnectionWrapper"
) -> None:
    servo_with_reconnect_force_restore.disconnect()

    script_path = "examples/ethernet/eth_store_restore.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"

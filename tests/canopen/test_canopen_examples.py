import pytest


@pytest.fixture
def arguments(read_config):
    protocol_contents = read_config["canopen"]
    dictionary = protocol_contents["dictionary"]
    node_id = protocol_contents["node_id"]
    device = protocol_contents["device"]
    channel = protocol_contents["channel"]
    baudrate = protocol_contents["baudrate"]
    attrs = [
        f"--dictionary_path={dictionary}",
        f"--node_id={node_id}",
        f"--transceiver={device}",
        f"--baudrate={baudrate}",
        f"--channel={channel}",
    ]
    yield attrs


@pytest.mark.canopen
def test_connection_example(arguments, script_runner):
    script_path = "examples/canopen/can_connection.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0
    assert "Could not find any nodes" not in result.stdout


@pytest.mark.canopen
def test_disturbance_example(arguments, script_runner):
    script_path = "examples/canopen/can_disturbance.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0


@pytest.mark.canopen
def test_load_firmware_example(arguments, script_runner, mocker):
    mock = mocker.patch("ingenialink.canopen.network.CanopenNetwork.load_firmware")
    script_path = "examples/canopen/can_load_firmware.py"
    result = script_runner.run([script_path, "--firmware_path=./dummy.sfu", *arguments])
    assert result.returncode == 0
    mock.assert_called_once()


@pytest.mark.canopen
def test_load_save_config_example(arguments, script_runner):
    script_path = "examples/canopen/can_load_save_config.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0


@pytest.mark.canopen
def test_monitoring_example(arguments, script_runner):
    script_path = "examples/canopen/can_monitoring.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0


@pytest.mark.canopen
def test_store_restore_example(arguments, script_runner):
    script_path = "examples/canopen/can_store_restore.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0
    assert "Could not find any nodes" not in result.stdout

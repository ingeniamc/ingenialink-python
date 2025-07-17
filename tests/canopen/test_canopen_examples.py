import pytest


@pytest.fixture
def arguments(setup_descriptor):
    dictionary = setup_descriptor.dictionary
    node_id = setup_descriptor.node_id
    device = setup_descriptor.device
    channel = setup_descriptor.channel
    baudrate = setup_descriptor.baudrate
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
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"
    assert "Could not find any nodes" not in result.stdout


@pytest.mark.canopen
def test_disturbance_example(arguments, script_runner):
    script_path = "examples/canopen/can_disturbance.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"


@pytest.mark.canopen
def test_load_firmware_example(arguments, script_runner, mocker):
    mock = mocker.patch("ingenialink.canopen.network.CanopenNetwork.load_firmware")
    script_path = "examples/canopen/can_load_firmware.py"
    result = script_runner.run([script_path, "--firmware_path=./dummy.sfu", *arguments])
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"
    mock.assert_called_once()


@pytest.mark.canopen
def test_load_save_config_example(arguments, script_runner):
    script_path = "examples/canopen/can_load_save_config.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"


@pytest.mark.canopen
def test_monitoring_example(arguments, script_runner):
    script_path = "examples/canopen/can_monitoring.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"


@pytest.mark.canopen
def test_store_restore_example(arguments, script_runner):
    script_path = "examples/canopen/can_store_restore.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0, f"Script failed with stderr:\n{result.stderr}"
    assert "Could not find any nodes" not in result.stdout

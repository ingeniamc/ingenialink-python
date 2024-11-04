import pytest


@pytest.fixture
def arguments(read_config):
    protocol_contents = read_config["ethernet"]
    dictionary = protocol_contents["dictionary"]
    ip_address = protocol_contents["ip"]
    port = protocol_contents["port"]
    attrs = [f"--dictionary_path={dictionary}", f"--ip_address={ip_address}", f"--port={port}"]
    yield attrs


@pytest.mark.ethernet
def test_connection_example(arguments, script_runner):
    script_path = "examples/ethernet/eth_connection.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0


@pytest.mark.ethernet
def test_load_firmware_example(arguments, script_runner, mocker):
    mock = mocker.patch("ingenialink.ethernet.network.EthernetNetwork.load_firmware")
    script_path = "examples/ethernet/eth_load_firmware.py"
    result = script_runner.run([script_path, "--firmware_path=./dummy.sfu", arguments[1]])
    assert result.returncode == 0
    mock.assert_called_once()


@pytest.mark.ethernet
def test_load_save_config_example(arguments, script_runner):
    script_path = "examples/ethernet/eth_load_save_config.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0


@pytest.mark.ethernet
def test_monitoring_example(arguments, script_runner):
    script_path = "examples/ethernet/eth_monitoring.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0


@pytest.mark.ethernet
def test_store_restore_example(arguments, script_runner):
    script_path = "examples/ethernet/eth_store_restore.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0

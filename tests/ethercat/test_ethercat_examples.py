import pytest


@pytest.fixture()
def arguments(read_config):
    protocol_contents = read_config["ethercat"]
    ifname = protocol_contents["ifname"]
    slave_id = protocol_contents["slave"]
    dictionary = protocol_contents["dictionary"]
    return [f"--dictionary_path={dictionary}", f"--interface={ifname}", f"--slave_id={slave_id}"]


@pytest.mark.ethercat()
def test_connection_example(arguments, script_runner):
    script_path = "examples/ethercat/ecat_connection.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0


@pytest.mark.ethercat()
def test_load_firmware_example(arguments, script_runner, mocker, read_config):
    slave_id = read_config["ethercat"]["slave"]
    mock = mocker.patch("ingenialink.ethercat.network.EthercatNetwork.load_firmware")
    arguments[0] = "--firmware_path=dummy_file.lfu"
    script_path = "examples/ethercat/ecat_load_firmware.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0
    mock.assert_called_once_with("dummy_file.lfu", False, slave_id=slave_id)


@pytest.mark.ethercat()
def test_pdo_example(read_config, script_runner):
    protocol_contents = read_config["ethercat"]
    ifname = protocol_contents["ifname"]
    dictionary = protocol_contents["dictionary"]
    script_path = "examples/ethercat/process_data_objects.py"
    result = script_runner.run(
        [script_path, f"--interface={ifname}", f"--dictionary_path={dictionary}", "--auto_stop"],
    )
    assert result.returncode == 0

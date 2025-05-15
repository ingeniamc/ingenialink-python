import pytest


@pytest.fixture
def arguments(setup_descriptor):
    attrs = [
        f"--dictionary_path={setup_descriptor.dictionary}",
        f"--interface={setup_descriptor.ifname}",
        f"--slave_id={setup_descriptor.slave}",
    ]
    yield attrs


@pytest.mark.ethercat
def test_connection_example(arguments, script_runner):
    script_path = "examples/ethercat/ecat_connection.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0


@pytest.mark.ethercat
def test_load_firmware_example(arguments, script_runner, mocker, setup_descriptor):
    slave_id = setup_descriptor.slave
    mock = mocker.patch("ingenialink.ethercat.network.EthercatNetwork.load_firmware")
    arguments[0] = "--firmware_path=dummy_file.lfu"
    script_path = "examples/ethercat/ecat_load_firmware.py"
    result = script_runner.run([script_path, *arguments])
    assert result.returncode == 0
    mock.assert_called_once_with("dummy_file.lfu", False, slave_id=slave_id)


@pytest.mark.multislave
def test_pdo_example(setup_descriptor, script_runner):
    script_path = "examples/ethercat/process_data_objects.py"
    result = script_runner.run([
        script_path,
        f"--interface={setup_descriptor.drives[0].ifname}",
        f"--dictionary_path={setup_descriptor.drives[0].dictionary}",
        "--auto_stop",
    ])
    assert result.returncode == 0

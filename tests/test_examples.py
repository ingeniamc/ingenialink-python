import pytest


@pytest.mark.ethercat
def test_pdo_example(read_config, script_runner):
    script_path = "examples/ethercat/process_data_objects.py"
    protocol_contents = read_config["ethercat"]
    ifname = protocol_contents["ifname"]
    dictionary = protocol_contents["dictionary"]
    result = script_runner.run(
        script_path, f"-ifname={ifname}", f"-dict={dictionary}", "-auto_stop"
    )
    assert result.returncode == 0

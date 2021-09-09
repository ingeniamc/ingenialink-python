def test_connect_to_slave(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    fw_version = servo.read('DRV_ID_SOFTWARE_VERSION')
    assert fw_version is not None and fw_version != ''
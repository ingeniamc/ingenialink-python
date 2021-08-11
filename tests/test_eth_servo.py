import pytest
import os

from ingenialink.ethernet.network import EthernetNetwork


def test_load_configuration():
    network = EthernetNetwork()
    r, servo = network.connect_to_slave("192.168.2.22",
                                        "resources/eve-xcr-e_eoe_1.8.1.xdf")
    if r >= 0:
        r = servo.load_configuration("resources/eve-xcr-e_1.8.1_cfg.xcf")
    assert r >= 0


def test_save_configuration():
    network = EthernetNetwork()
    r, servo = network.connect_to_slave("192.168.2.22",
                                        "resources/eve-xcr-e_eoe_1.8.1.xdf")
    if r >= 0:
        # Remove possible already saved output configuration
        try:
            os.remove("resources/output_cfg.xcf")
        except:
            pass
        r = servo.save_configuration("resources/output_cfg.xcf")
    assert r >= 0

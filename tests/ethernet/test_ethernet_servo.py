from ipaddress import NetmaskValueError

import pytest


@pytest.mark.ethernet
@pytest.mark.parametrize(
    "ip_address, gateway", [("192.168.2.xx", "192.168.2.1"), ("192.168.2.22", "192.168.3.1")]
)
def test_change_tcp_ip_parameters_value_error(servo, ip_address, gateway):
    with pytest.raises(ValueError):
        servo.change_tcp_ip_parameters(ip_address, "255.255.255.0", gateway)


@pytest.mark.ethernet
def test_change_tcp_ip_parameters_invalid_netmask(servo):
    with pytest.raises(NetmaskValueError):
        servo.change_tcp_ip_parameters("192.168.2.22", "255.255.255.xx", "192.168.2.1")

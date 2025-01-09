import re
from ipaddress import NetmaskValueError

import pytest


@pytest.mark.ethernet()
@pytest.mark.parametrize(
    ("ip_address", "gateway"),
    [("192.168.2.22", "192.168.3.1")],
)
def test_change_tcp_ip_parameters_value_error(connect_to_slave, ip_address, gateway):
    servo, net = connect_to_slave
    with pytest.raises(
        ValueError,
        match=re.escape(
            f"Drive IP {ip_address} and Gateway IP {gateway} are not on the same network."
        ),
    ):
        servo.change_tcp_ip_parameters(ip_address, "255.255.255.0", gateway)


@pytest.mark.ethernet()
@pytest.mark.parametrize(
    ("ip_address", "gateway"),
    [("192.168.2.xx", "192.168.2.1")],
)
def test_change_tcp_ip_parameters_invalid_ip(connect_to_slave, ip_address, gateway):
    servo, net = connect_to_slave
    with pytest.raises(
        ValueError,
        match=re.escape(f"{ip_address} does not appear to be an IPv4 or IPv6 address"),
    ):
        servo.change_tcp_ip_parameters(ip_address, "255.255.255.0", gateway)


@pytest.mark.ethernet()
def test_change_tcp_ip_parameters_invalid_netmask(connect_to_slave):
    servo, net = connect_to_slave
    with pytest.raises(NetmaskValueError):
        servo.change_tcp_ip_parameters("192.168.2.22", "255.255.255.xx", "192.168.2.1")

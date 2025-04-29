from pathlib import Path

from summit_testing_framework.setups import LocalDriveConfigSpecifier
from summit_testing_framework.setups.specifiers import VirtualDriveSpecifier

VIRTUAL_DRIVE_SETUP = VirtualDriveSpecifier(ip="127.0.0.1", port=1061)

DEN_NET_E_SETUP = LocalDriveConfigSpecifier.from_ethercat_configuration(
    identifier="den-net-e",
    dictionary=Path("C://Users//julieta.prieto//Downloads//den-net-e_eoe_2.7.3.xdf"),
    config_file=Path("C://Users//julieta.prieto//Downloads//den_net_e.xcf"),
    firmware_file=Path("C://Users//julieta.prieto//Downloads//den-net-e_2.7.3.lfu"),
    ifname="\\Device\\NPF_{675921D7-B64A-4997-9211-D18E2A6DC96A}",
    slave=1,
    boot_in_app=False,
)

CAP_NET_E_SETUP = LocalDriveConfigSpecifier.from_ethercat_configuration(
    identifier="cap-net-e",
    dictionary=Path("C://Users//julieta.prieto//Downloads//cap-net-e_eoe_2.7.2.xdf"),
    config_file=Path("C://Users//julieta.prieto//Downloads//cap_net_e.xcf"),
    firmware_file=Path("C://Users//julieta.prieto//Downloads//cap-net-e_2.7.2.sfu"),
    ifname="\\Device\\NPF_{675921D7-B64A-4997-9211-D18E2A6DC96A}",
    slave=1,
    boot_in_app=False,
)

DEN_S_NET_E_SETUP = LocalDriveConfigSpecifier.from_ethercat_configuration(
    identifier="den-s-net-e",
    dictionary=Path("C://Users//julieta.prieto//Downloads//DEN-S-NET-E.xdf"),
    config_file=Path("C://Users//julieta.prieto//Downloads//den_s_net_e.xcf"),
    firmware_file=Path(
        "//azr-srv-ingfs1//dist//products//i050_summit//i056_den-s-net//firmware//release//2.7.3.1//den-s-net-e_2.7.3.lfu"
    ),
    ifname="\\Device\\NPF_{675921D7-B64A-4997-9211-D18E2A6DC96A}",
    slave=1,
    boot_in_app=False,
)


TESTS_SETUP = VIRTUAL_DRIVE_SETUP

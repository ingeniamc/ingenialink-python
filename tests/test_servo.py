import os
import re
import shutil
import time
from pathlib import Path
from xml.etree import ElementTree

import pytest
from packaging import version

from ingenialink import RegAccess
from ingenialink.canopen.servo import CanopenServo
from ingenialink.configuration_file import ConfigurationFile
from ingenialink.ethernet.register import RegDtype
from ingenialink.exceptions import (
    ILConfigurationError,
    ILError,
    ILIOError,
    ILStateError,
    ILTimeoutError,
    ILValueError,
)
from ingenialink.register import RegAddressType
from ingenialink.servo import Servo, ServoState
from tests.virtual.test_virtual_network import RESOURCES_FOLDER

MONITORING_CH_DATA_SIZE = 4
MONITORING_NUM_SAMPLES = 100
DISTURBANCE_CH_DATA_SIZE = 4
DISTURBANCE_NUM_SAMPLES = 100


class RegisterUpdateTest:
    def __init__(self):
        self.call_count = 0
        self.servo = None
        self.register = None

    def register_update_test(self, servo, register, value):
        self.servo = servo
        self.register = register
        self.value = value
        self.call_count += 1


def _clean(filename):
    if os.path.isfile(filename):
        os.remove(filename)


def _get_reg_address(register, protocol):
    attr_dict = {"ethernet": "address", "canopen": "idx"}
    return getattr(register, attr_dict[protocol])


def wait_until_alive(servo, timeout=None):
    init_time = time.time()
    while not servo.is_alive():
        if timeout is not None and (init_time + timeout) < time.time():
            pytest.fail("The drive is unresponsive after the recovery timeout.")
        time.sleep(1)


def skip_if_monitoring_is_not_available(servo):
    try:
        servo.read("MON_DIST_STATUS")
    except ILError:
        pytest.skip("Monitoring is not available")


class SDOReadTimeoutManager:
    def __init__(self, network, new_value):
        self.__net = network
        self.__new_value = int(1_000_000 * new_value)
        self.__initial_value = self.__net._ecat_master.sdo_read_timeout

    def __enter__(self):
        self.__net._ecat_master.sdo_read_timeout = self.__new_value
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.__net._ecat_master.sdo_read_timeout = self.__initial_value


@pytest.fixture()
def create_monitoring(connect_to_slave, pytestconfig):
    protocol = pytestconfig.getoption("--protocol")
    servo, net = connect_to_slave
    skip_if_monitoring_is_not_available(servo)
    servo.monitoring_disable()
    servo.monitoring_remove_all_mapped_registers()
    registers_key = ["CL_CUR_D_REF_VALUE"]
    subnode = 1
    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        address = _get_reg_address(reg, protocol)
        servo.monitoring_set_mapped_register(
            idx, address, subnode, reg.dtype.value, MONITORING_CH_DATA_SIZE
        )
    divisor = 1
    servo.write("MON_DIST_FREQ_DIV", divisor, subnode=0)
    servo.write("MON_CFG_SOC_TYPE", 0, subnode=0)
    servo.write("MON_CFG_WINDOW_SAMP", MONITORING_NUM_SAMPLES, subnode=0)
    yield servo, net
    servo.monitoring_disable()


@pytest.fixture()
def create_disturbance(connect_to_slave, pytestconfig):
    protocol = pytestconfig.getoption("--protocol")
    servo, net = connect_to_slave
    skip_if_monitoring_is_not_available(servo)
    data = list(range(DISTURBANCE_NUM_SAMPLES))
    servo.disturbance_disable()
    servo.disturbance_remove_all_mapped_registers()
    reg = servo._get_reg("CL_POS_SET_POINT_VALUE", subnode=1)
    address = _get_reg_address(reg, protocol)
    servo.disturbance_set_mapped_register(
        0, address, 1, RegDtype.S32.value, DISTURBANCE_CH_DATA_SIZE
    )
    servo.disturbance_write_data(0, RegDtype.S32, data)
    yield servo, net
    servo.disturbance_disable()


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_save_configuration(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    filename = "temp_config"

    servo.save_configuration(filename)

    assert os.path.isfile(filename)

    config_file = ConfigurationFile.from_xcf(filename)

    prod_code, rev_number = servo._get_drive_identification()
    assert config_file.device.product_code == prod_code
    assert config_file.device.revision_number == rev_number

    assert config_file.device.part_number == servo.dictionary.part_number
    interface = servo.DICTIONARY_INTERFACE_ATTR_CAN
    assert config_file.device.interface == interface
    # The firmware version from the drive has trailing zeros
    # and the one from the dictionary does not
    assert version.parse(config_file.device.firmware_version) == version.parse(
        servo.dictionary.firmware_version
    )

    assert len(config_file.registers) > 0
    for saved_register in config_file.registers:
        subnode = saved_register.subnode

        reg_id = saved_register.uid
        registers = servo.dictionary.registers(subnode=subnode)
        assert reg_id in registers
        assert registers[reg_id].storage == saved_register.storage
        assert registers[reg_id].access == saved_register.access
        assert registers[reg_id].dtype == saved_register.dtype
        assert saved_register.access == RegAccess.RW
        assert registers[reg_id].address_type != RegAddressType.NVM_NONE

    _clean(filename)


@pytest.mark.no_connection
def test_check_configuration(virtual_drive):
    server, servo = virtual_drive

    assert servo is not None and server is not None

    filename = "temp_config"

    # Load the configuration, the subsequent check should not raise an error.
    servo.save_configuration(filename)
    servo.check_configuration(filename)

    # Change a random register
    register = "DRV_PROT_USER_OVER_VOLT"
    new_value = 10.0
    servo.write(register, data=new_value, subnode=1)

    check_failed_message = re.escape("Configuration check failed for the following registers:")

    # The check should fail for this register
    with pytest.raises(
        ILConfigurationError,
        match=check_failed_message
        + r"\n"
        + register
        + r" --- Expected: \d*\.\d+ | Found: "
        + str(new_value),
    ):
        servo.check_configuration(filename)

    # Load the configuration again to reset the changes we just made
    # The subsequent check should no longer raise an error.
    servo.load_configuration(filename)
    servo.check_configuration(filename)


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_load_configuration(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    filename = "temp_config"

    servo.save_configuration(filename)

    assert os.path.isfile(filename)

    servo.load_configuration(filename)

    _, loaded_registers = servo._read_configuration_file(filename)

    for register in loaded_registers:
        reg_id = register.attrib.get("id")
        storage = register.attrib.get("storage")
        subnode = int(register.attrib.get("subnode"))
        dtype = register.attrib.get("dtype")

        # Check if the register exists in the drive
        try:
            value = servo.read(reg_id, subnode=subnode)
        except ILIOError:
            continue

        if dtype == "str":
            assert value == storage
        elif dtype == "float":
            assert value == pytest.approx(float(storage), 0.0001)
        else:
            assert value == int(storage)

    _clean(filename)


@pytest.mark.no_connection
def test_load_configuration_strict(mocker, virtual_drive_custom_dict):  # noqa: F811
    dictionary = os.path.join(RESOURCES_FOLDER, "virtual_drive.xdf")
    server, net, servo = virtual_drive_custom_dict(dictionary)
    test_file = "./tests/resources/test_config_file.xcf"
    mocker.patch("ingenialink.servo.Servo.write", side_effect=ILError("Error writing"))
    with pytest.raises(ILError) as exc_info:
        servo.load_configuration(test_file, strict=True)
    assert (
        str(exc_info.value) == "Exception during load_configuration, "
        "register DRV_DIAG_SYS_ERROR_TOTAL_COM: Error writing"
    )


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_load_configuration_file_not_found(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    filename = "can_config.xdf"
    with pytest.raises(FileNotFoundError):
        servo.load_configuration(filename)


@pytest.mark.parametrize("subnode", [-1, "1"])
@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_load_configuration_invalid_subnode(read_config, pytestconfig, connect_to_slave, subnode):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    protocol = pytestconfig.getoption("--protocol")
    filename = read_config[protocol]["load_config_file"]
    with pytest.raises(ValueError):
        servo.load_configuration(filename, subnode=subnode)


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_load_configuration_to_subnode_zero(read_config, pytestconfig, connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    protocol = pytestconfig.getoption("--protocol")
    filename = read_config[protocol]["load_config_file"]
    path = Path(filename)
    file = filename.split("/")[-1]
    modified_path = Path(filename.replace(file, "config_0_test.xdf"))
    shutil.copy(path, modified_path)
    with open(modified_path, encoding="utf-8") as xml_file:
        tree = ElementTree.parse(xml_file)
        root = tree.getroot()
        axis = tree.findall("*/Device/Axes/Axis")
        if axis:
            # Multiaxis
            registers = root.findall("./Body/Device/Axes/Axis/Registers/Register")
        else:
            # Single axis
            registers = root.findall("./Body/Device/Registers/Register")
        for element in registers:
            element.attrib["subnode"] = "1"
        tree.write(modified_path)
    with pytest.raises(ValueError):
        servo.load_configuration(str(modified_path), subnode=0)


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_store_parameters(connect_to_slave, connect_to_rack_service):
    user_over_voltage_register = "DRV_PROT_USER_OVER_VOLT"

    servo, net = connect_to_slave

    initial_user_over_voltage_value = servo.read(user_over_voltage_register)
    new_user_over_voltage_value = initial_user_over_voltage_value + 5

    servo.write(user_over_voltage_register, new_user_over_voltage_value)

    assert servo.read(user_over_voltage_register) == new_user_over_voltage_value

    servo.store_parameters()

    time.sleep(5)

    client = connect_to_rack_service
    client.exposed_turn_off_ps()
    time.sleep(1)
    client.exposed_turn_on_ps()

    wait_until_alive(servo, timeout=20)

    assert servo.read(user_over_voltage_register) == new_user_over_voltage_value


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_restore_parameters(connect_to_slave, connect_to_rack_service):
    user_over_voltage_register = "DRV_PROT_USER_OVER_VOLT"

    servo, net = connect_to_slave

    new_user_over_voltage_value = servo.read(user_over_voltage_register) + 5

    servo.write(user_over_voltage_register, new_user_over_voltage_value)

    assert servo.read(user_over_voltage_register) == new_user_over_voltage_value

    servo.restore_parameters()

    client = connect_to_rack_service
    client.exposed_turn_off_ps()
    time.sleep(1)
    client.exposed_turn_on_ps()

    wait_until_alive(servo, timeout=20)

    assert servo.read(user_over_voltage_register) != new_user_over_voltage_value


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_read(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    value = servo.read("DRV_STATE_STATUS")
    assert value is not None


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_write(connect_to_slave):
    servo, net = connect_to_slave
    assert servo is not None and net is not None

    reg = "CL_AUX_FBK_SENSOR"
    value = 4

    saved_value = servo.read(reg)
    value = value + 1 if saved_value == value else value

    servo.write(reg, value)
    saved_value = servo.read(reg)

    assert value == saved_value


@pytest.mark.ethernet
@pytest.mark.canopen
@pytest.mark.ethercat
def test_monitoring_enable_disable(connect_to_slave):
    servo, net = connect_to_slave
    skip_if_monitoring_is_not_available(servo)
    servo.monitoring_enable()
    assert servo.read(servo.MONITORING_DIST_ENABLE, subnode=0) == 1
    servo.monitoring_disable()
    assert servo.read(servo.MONITORING_DIST_ENABLE, subnode=0) == 0


@pytest.mark.ethernet
@pytest.mark.canopen
@pytest.mark.ethercat
def test_monitoring_remove_data(create_monitoring):
    servo, net = create_monitoring
    servo.monitoring_enable()
    servo.write("MON_CMD_FORCE_TRIGGER", 1, subnode=0)
    assert servo.read("MON_CFG_BYTES_VALUE", subnode=0) > 0
    servo.monitoring_remove_data()
    assert servo.read("MON_CFG_BYTES_VALUE", subnode=0) == 0


@pytest.mark.ethernet
@pytest.mark.canopen
@pytest.mark.ethercat
def test_monitoring_map_register(connect_to_slave, pytestconfig):
    protocol = pytestconfig.getoption("--protocol")
    servo, net = connect_to_slave
    skip_if_monitoring_is_not_available(servo)
    servo.monitoring_remove_all_mapped_registers()
    registers_key = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE"]
    data_size = 4
    subnode = 1
    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        address = _get_reg_address(reg, protocol)
        servo.monitoring_set_mapped_register(idx, address, subnode, reg.dtype.value, data_size)
    assert servo.monitoring_number_mapped_registers == len(registers_key)

    mon_cfg_regs = {"MON_CFG_REG0_MAP": 0x10200504, "MON_CFG_REG1_MAP": 0x10210804}
    for key, value in mon_cfg_regs.items():
        assert servo.read(key, 0) == value

    assert servo.read("MON_CFG_TOTAL_MAP", 0) == len(registers_key)

    servo.monitoring_remove_all_mapped_registers()
    assert servo.monitoring_number_mapped_registers == 0
    assert servo.read("MON_CFG_TOTAL_MAP", 0) == 0


@pytest.mark.ethernet
@pytest.mark.canopen
@pytest.mark.ethercat
def test_monitoring_data_size(create_monitoring):
    servo, net = create_monitoring
    servo.monitoring_enable()
    servo.write("MON_CMD_FORCE_TRIGGER", 1, subnode=0)
    assert servo.monitoring_get_bytes_per_block() == MONITORING_CH_DATA_SIZE
    assert servo.monitoring_actual_number_bytes() > 0
    assert servo.monitoring_data_size == MONITORING_CH_DATA_SIZE * MONITORING_NUM_SAMPLES
    servo.monitoring_remove_data()


@pytest.mark.ethernet
@pytest.mark.canopen
@pytest.mark.ethercat
def test_monitoring_read_data(create_monitoring):
    servo, net = create_monitoring
    servo.monitoring_enable()
    servo.write("MON_CMD_FORCE_TRIGGER", 1, subnode=0)
    time.sleep(1)
    servo.monitoring_read_data()
    servo.monitoring_disable()
    data = servo.monitoring_channel_data(0)

    assert isinstance(data, list)
    assert len(data) == pytest.approx(MONITORING_NUM_SAMPLES, 1)
    assert isinstance(data[0], float)
    servo.monitoring_remove_data()


@pytest.mark.ethernet
@pytest.mark.canopen
@pytest.mark.ethercat
def test_disturbance_enable_disable(connect_to_slave):
    servo, net = connect_to_slave
    skip_if_monitoring_is_not_available(servo)
    servo.disturbance_enable()
    assert servo.read(servo.DISTURBANCE_ENABLE, subnode=0) == 1
    servo.disturbance_disable()
    assert servo.read(servo.DISTURBANCE_ENABLE, subnode=0) == 0


@pytest.mark.ethernet
@pytest.mark.canopen
@pytest.mark.ethercat
def test_disturbance_remove_data(create_disturbance):
    servo, net = create_disturbance
    servo.disturbance_enable()
    assert (
        servo.read("DIST_CFG_BYTES", subnode=0)
        == DISTURBANCE_CH_DATA_SIZE * DISTURBANCE_NUM_SAMPLES
    )
    servo.disturbance_remove_data()
    assert servo.read("DIST_CFG_BYTES", subnode=0) == 0


@pytest.mark.ethernet
@pytest.mark.canopen
@pytest.mark.ethercat
def test_disturbance_map_register(connect_to_slave, pytestconfig):
    protocol = pytestconfig.getoption("--protocol")
    servo, net = connect_to_slave
    skip_if_monitoring_is_not_available(servo)
    servo.disturbance_remove_all_mapped_registers()
    registers_key = ["CL_POS_SET_POINT_VALUE", "CL_VEL_SET_POINT_VALUE"]
    data_size = 4
    subnode = 1
    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        address = _get_reg_address(reg, protocol)
        servo.disturbance_set_mapped_register(idx, address, subnode, reg.dtype.value, data_size)
    assert servo.disturbance_number_mapped_registers == len(registers_key)

    dist_cfg_regs = {"DIST_CFG_REG0_MAP": 0x10200504, "DIST_CFG_REG1_MAP": 0x10210804}
    for key, value in dist_cfg_regs.items():
        assert servo.read(key, 0) == value

    assert servo.read("DIST_CFG_MAP_REGS", 0) == len(registers_key)

    servo.disturbance_remove_all_mapped_registers()
    assert servo.disturbance_number_mapped_registers == 0
    assert servo.read("DIST_CFG_MAP_REGS", 0) == 0


@pytest.mark.ethernet
@pytest.mark.canopen
@pytest.mark.ethercat
def test_disturbance_data_size(create_disturbance):
    servo, net = create_disturbance
    servo.disturbance_enable()
    assert servo.disturbance_data_size == DISTURBANCE_CH_DATA_SIZE * DISTURBANCE_NUM_SAMPLES
    servo.disturbance_remove_data()


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_enable_disable(connect_to_slave):
    servo, net = connect_to_slave
    servo.enable()
    assert servo.status[1] == ServoState.ENABLED
    servo.disable()
    assert servo.status[1] == ServoState.DISABLED


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_fault_reset(connect_to_slave, get_configuration_from_rack_service):
    drive_idx, config = get_configuration_from_rack_service
    drive = config[drive_idx]
    if drive.identifier == "eve-xcr-e":
        pytest.skip("There is a specific fault test for the EVE-XCR-E")
    servo, net = connect_to_slave
    prev_val = servo.read("DRV_PROT_USER_OVER_VOLT", subnode=1)
    servo.write("DRV_PROT_USER_OVER_VOLT", data=10.0, subnode=1)
    with pytest.raises(ILStateError):
        servo.enable()
    servo.fault_reset()
    assert servo.status[1] != ServoState.FAULT
    servo.write("DRV_PROT_USER_OVER_VOLT", data=prev_val, subnode=1)


@pytest.mark.ethercat
def test_fault_reset_eve_xcr(connect_to_slave, get_configuration_from_rack_service):
    drive_idx, config = get_configuration_from_rack_service
    drive = config[drive_idx]
    if drive.identifier != "eve-xcr-e":
        pytest.skip("The test is only for the EVE-XCR-E")
    servo, net = connect_to_slave
    prev_val = servo.read("DRV_PROT_USER_OVER_VOLT", subnode=1)
    servo.write("DRV_PROT_USER_OVER_VOLT", data=10.0, subnode=1)
    with SDOReadTimeoutManager(network=net, new_value=net.DEFAULT_ECAT_CONNECTION_TIMEOUT_S * 2):
        with pytest.raises(ILStateError):
            servo.enable()
        servo.fault_reset()
    assert servo.status[1] != ServoState.FAULT
    servo.write("DRV_PROT_USER_OVER_VOLT", data=prev_val, subnode=1)


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_is_alive(connect_to_slave):
    servo, net = connect_to_slave
    assert servo.is_alive()


@pytest.mark.canopen
@pytest.mark.ethernet
@pytest.mark.ethercat
def test_status_word_wait_change(connect_to_slave):
    servo, net = connect_to_slave
    subnode = 1
    timeout = 0.5
    status_word = servo.read(servo.STATUS_WORD_REGISTERS, subnode=subnode)
    with pytest.raises(ILTimeoutError):
        servo.status_word_wait_change(status_word, timeout, subnode)


@pytest.mark.ethernet
@pytest.mark.canopen
@pytest.mark.ethercat
def test_disturbance_overflow(connect_to_slave, pytestconfig):
    protocol = pytestconfig.getoption("--protocol")
    servo, net = connect_to_slave
    skip_if_monitoring_is_not_available(servo)
    servo.disturbance_disable()
    servo.disturbance_remove_all_mapped_registers()
    reg = servo._get_reg("DRV_OP_CMD", subnode=1)
    address = _get_reg_address(reg, protocol)
    servo.disturbance_set_mapped_register(
        0, address, 1, RegDtype.U16.value, DISTURBANCE_CH_DATA_SIZE
    )
    data = list(range(-10, 11))
    with pytest.raises(ILValueError):
        servo.disturbance_write_data(0, RegDtype.U16, data)


@pytest.mark.no_connection
def test_subscribe_register_updates(virtual_drive_custom_dict):  # noqa: F811
    user_over_voltage_uid = "DRV_PROT_USER_OVER_VOLT"
    register_update_callback = RegisterUpdateTest()

    dictionary = os.path.join(RESOURCES_FOLDER, "virtual_drive.xdf")
    server, net, servo = virtual_drive_custom_dict(dictionary)
    servo.register_update_subscribe(register_update_callback.register_update_test)

    previous_reg_value = servo.read(user_over_voltage_uid, subnode=1)
    assert register_update_callback.call_count == 1
    assert register_update_callback.servo == servo
    assert register_update_callback.register.identifier == user_over_voltage_uid
    assert register_update_callback.value == previous_reg_value

    new_reg_value = 100
    servo.write(user_over_voltage_uid, data=new_reg_value, subnode=1)
    assert register_update_callback.call_count == 2
    assert register_update_callback.servo == servo
    assert register_update_callback.register.identifier == user_over_voltage_uid
    assert register_update_callback.value == new_reg_value

    servo.register_update_unsubscribe(register_update_callback.register_update_test)

    servo.write(user_over_voltage_uid, data=previous_reg_value, subnode=1)


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "status_word, state",
    [
        (
            {
                Servo.STATUS_WORD_READY_TO_SWITCH_ON: 0,
                Servo.STATUS_WORD_SWITCHED_ON: 0,
                Servo.STATUS_WORD_OPERATION_ENABLED: 0,
                Servo.STATUS_WORD_FAULT: 0,
                "VOLTAGE_ENABLED": 1,
                Servo.STATUS_WORD_QUICK_STOP: 1,
                Servo.STATUS_WORD_SWITCH_ON_DISABLED: 0,
                "WARNING": 1,
                "TARGET_REACHED": 0,
                "SWITCH_LIMITS_ACTIVE": 0,
                "COMMUTATION_FEEDBACK_ALIGNED": 0,
            },
            ServoState.NRDY,
        ),
        (
            {
                Servo.STATUS_WORD_READY_TO_SWITCH_ON: 0,
                Servo.STATUS_WORD_SWITCHED_ON: 0,
                Servo.STATUS_WORD_OPERATION_ENABLED: 0,
                Servo.STATUS_WORD_FAULT: 0,
                "VOLTAGE_ENABLED": 1,
                Servo.STATUS_WORD_QUICK_STOP: 1,
                Servo.STATUS_WORD_SWITCH_ON_DISABLED: 1,
                "WARNING": 0,
                "TARGET_REACHED": 0,
                "SWITCH_LIMITS_ACTIVE": 0,
                "COMMUTATION_FEEDBACK_ALIGNED": 0,
            },
            ServoState.DISABLED,
        ),
        (
            {
                Servo.STATUS_WORD_READY_TO_SWITCH_ON: 1,
                Servo.STATUS_WORD_SWITCHED_ON: 0,
                Servo.STATUS_WORD_OPERATION_ENABLED: 0,
                Servo.STATUS_WORD_FAULT: 0,
                "VOLTAGE_ENABLED": 1,
                Servo.STATUS_WORD_QUICK_STOP: 1,
                Servo.STATUS_WORD_SWITCH_ON_DISABLED: 0,
                "WARNING": 0,
                "TARGET_REACHED": 1,
                "SWITCH_LIMITS_ACTIVE": 0,
                "COMMUTATION_FEEDBACK_ALIGNED": 0,
            },
            ServoState.RDY,
        ),
        (
            {
                Servo.STATUS_WORD_READY_TO_SWITCH_ON: 1,
                Servo.STATUS_WORD_SWITCHED_ON: 1,
                Servo.STATUS_WORD_OPERATION_ENABLED: 0,
                Servo.STATUS_WORD_FAULT: 0,
                "VOLTAGE_ENABLED": 1,
                Servo.STATUS_WORD_QUICK_STOP: 1,
                Servo.STATUS_WORD_SWITCH_ON_DISABLED: 0,
                "WARNING": 1,
                "TARGET_REACHED": 0,
                "SWITCH_LIMITS_ACTIVE": 0,
                "COMMUTATION_FEEDBACK_ALIGNED": 0,
            },
            ServoState.ON,
        ),
        (
            {
                Servo.STATUS_WORD_READY_TO_SWITCH_ON: 1,
                Servo.STATUS_WORD_SWITCHED_ON: 1,
                Servo.STATUS_WORD_OPERATION_ENABLED: 1,
                Servo.STATUS_WORD_FAULT: 0,
                "VOLTAGE_ENABLED": 0,
                Servo.STATUS_WORD_QUICK_STOP: 1,
                Servo.STATUS_WORD_SWITCH_ON_DISABLED: 0,
                "WARNING": 0,
                "TARGET_REACHED": 0,
                "SWITCH_LIMITS_ACTIVE": 0,
                "COMMUTATION_FEEDBACK_ALIGNED": 0,
            },
            ServoState.ENABLED,
        ),
        (
            {
                Servo.STATUS_WORD_READY_TO_SWITCH_ON: 1,
                Servo.STATUS_WORD_SWITCHED_ON: 1,
                Servo.STATUS_WORD_OPERATION_ENABLED: 1,
                Servo.STATUS_WORD_FAULT: 0,
                "VOLTAGE_ENABLED": 0,
                Servo.STATUS_WORD_QUICK_STOP: 0,
                Servo.STATUS_WORD_SWITCH_ON_DISABLED: 0,
                "WARNING": 0,
                "TARGET_REACHED": 0,
                "SWITCH_LIMITS_ACTIVE": 0,
                "COMMUTATION_FEEDBACK_ALIGNED": 0,
            },
            ServoState.QSTOP,
        ),
        (
            {
                Servo.STATUS_WORD_READY_TO_SWITCH_ON: 1,
                Servo.STATUS_WORD_SWITCHED_ON: 1,
                Servo.STATUS_WORD_OPERATION_ENABLED: 1,
                Servo.STATUS_WORD_FAULT: 1,
                "VOLTAGE_ENABLED": 1,
                Servo.STATUS_WORD_QUICK_STOP: 0,
                Servo.STATUS_WORD_SWITCH_ON_DISABLED: 0,
                "WARNING": 0,
                "TARGET_REACHED": 0,
                "SWITCH_LIMITS_ACTIVE": 0,
                "COMMUTATION_FEEDBACK_ALIGNED": 0,
            },
            ServoState.FAULTR,
        ),
        (
            {
                Servo.STATUS_WORD_READY_TO_SWITCH_ON: 0,
                Servo.STATUS_WORD_SWITCHED_ON: 0,
                Servo.STATUS_WORD_OPERATION_ENABLED: 0,
                Servo.STATUS_WORD_FAULT: 1,
                "VOLTAGE_ENABLED": 0,
                Servo.STATUS_WORD_QUICK_STOP: 1,
                Servo.STATUS_WORD_SWITCH_ON_DISABLED: 0,
                "WARNING": 0,
                "TARGET_REACHED": 0,
                "SWITCH_LIMITS_ACTIVE": 0,
                "COMMUTATION_FEEDBACK_ALIGNED": 0,
            },
            ServoState.FAULT,
        ),
    ],
)
def test_status_word_decode(virtual_drive, status_word, state):
    server, servo = virtual_drive
    assert servo.status_word_decode(status_word) == state

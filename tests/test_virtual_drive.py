import time

import numpy as np
import pytest
from scipy import signal

from ingenialink.enums.register import REG_DTYPE
from ingenialink.enums.servo import SERVO_STATE
from virtual_drive.core import OperationMode

MONITORING_CH_DATA_SIZE = 4
MONITORING_NUM_SAMPLES = 100
DISTURBANCE_CH_DATA_SIZE = 4


def create_monitoring_disturbance(servo, dist_reg, monit_regs, dist_data):
    divisor = 1

    reg = servo._get_reg(dist_reg, subnode=1)
    servo.disturbance_disable()
    servo.disturbance_remove_all_mapped_registers()
    servo.write("DIST_FREQ_DIV", divisor, subnode=0)
    servo.disturbance_set_mapped_register(0, reg.address, reg.subnode, reg.dtype.value, 4)
    servo.disturbance_write_data([0], [reg.dtype], [dist_data])
    servo.disturbance_enable()

    servo.monitoring_disable()
    for idx, key in enumerate(monit_regs):
        reg = servo._get_reg(key, subnode=1)
        servo.monitoring_set_mapped_register(
            idx, reg.address, reg.subnode, reg.dtype.value, MONITORING_CH_DATA_SIZE
        )

    servo.write("MON_DIST_FREQ_DIV", divisor, subnode=0)
    servo.write("MON_CFG_SOC_TYPE", 1, subnode=0)
    servo.write("MON_CFG_WINDOW_SAMP", MONITORING_NUM_SAMPLES, subnode=0)


@pytest.mark.no_connection
def test_connect_to_virtual(virtual_drive):
    _, servo = virtual_drive
    time.sleep(1)
    servo.write("CL_AUX_FBK_SENSOR", 4)
    servo.write("DIST_CFG_REG0_MAP", 4, 0)


@pytest.mark.parametrize(
    "reg, value, subnode", [("CL_AUX_FBK_SENSOR", 4, 1), ("DIST_CFG_REG0_MAP", 4, 0)]
)
@pytest.mark.no_connection
def test_virtual_drive_write_read(virtual_drive, reg, value, subnode):
    _, virtual_servo = virtual_drive

    virtual_servo.write(reg, value, subnode)
    response = virtual_servo.read(reg, subnode)

    assert response == value


@pytest.mark.no_connection
def test_virtual_drive_write_wrong_enum(virtual_drive):
    _, virtual_servo = virtual_drive

    register = "FBK_GEN_MODE"
    subnode = 1

    assert virtual_servo.read(register, subnode) == 0
    virtual_servo.write(register, 1, subnode)
    assert virtual_servo.read(register, subnode) == 1
    virtual_servo.write(register, 5, subnode)
    assert virtual_servo.read(register, subnode) == 5


@pytest.mark.ethernet
@pytest.mark.parametrize(
    "reg, value, subnode", [("CL_AUX_FBK_SENSOR", 4, 1), ("DIST_CFG_REG0_MAP", 4, 0)]
)
def test_virtual_drive_write_read_compare_responses(
    connect_to_slave, virtual_drive, reg, value, subnode
):
    servo, _ = connect_to_slave
    _, virtual_servo = virtual_drive

    virtual_response = virtual_servo.write(reg, value, subnode)
    response = servo.write(reg, value, subnode)
    assert response == virtual_response

    response = servo.read(reg, subnode)
    virtual_response = virtual_servo.read(reg, subnode)
    assert response == virtual_response

    new_value = virtual_response + 1
    virtual_servo.write(reg, new_value, subnode)
    saved_value = virtual_servo.read(reg, subnode)
    assert saved_value == new_value


@pytest.mark.no_connection
@pytest.mark.parametrize("divisor", [1, 2])
def test_virtual_monitoring(virtual_drive, divisor):
    _, servo = virtual_drive

    servo.monitoring_disable()
    registers_key = ["CL_POS_FBK_VALUE", "CL_VEL_FBK_VALUE"]
    subnode = 1
    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        address = reg.address
        servo.monitoring_set_mapped_register(
            idx, address, subnode, reg.dtype.value, MONITORING_CH_DATA_SIZE
        )

    servo.write("MON_DIST_FREQ_DIV", divisor, subnode=0)
    servo.write("MON_CFG_SOC_TYPE", 1, subnode=0)
    servo.write("MON_CFG_WINDOW_SAMP", MONITORING_NUM_SAMPLES, subnode=0)

    servo.monitoring_enable()
    servo.write("MON_CMD_FORCE_TRIGGER", 1, subnode=0)
    time.sleep(0.1)
    servo.monitoring_read_data()
    servo.monitoring_disable()

    for idx, key in enumerate(registers_key):
        reg = servo._get_reg(key, subnode=1)
        address = reg.address
        subnode = reg.subnode
        data = servo.monitoring_channel_data(idx)
        expected_data = [
            subnode + address + i for i in range(0, MONITORING_NUM_SAMPLES * divisor, divisor)
        ]
        assert data == expected_data


@pytest.mark.no_connection
@pytest.mark.parametrize("register_key", ["CL_VEL_FBK_VALUE", "CL_POS_FBK_VALUE"])
def test_virtual_disturbance(virtual_drive, register_key):
    server, servo = virtual_drive

    servo.disturbance_disable()
    servo.disturbance_remove_all_mapped_registers()

    subnode = 1
    reg = servo._get_reg(register_key, subnode=1)
    address = reg.address
    servo.disturbance_set_mapped_register(0, address, subnode, reg.dtype.value, 4)
    if reg.dtype == REG_DTYPE.FLOAT:
        data_arr = [0.0, -1.0, 2.0, 3.0]
    else:
        data_arr = [0, -1, 2, 3]

    channels = [0]
    servo.disturbance_write_data(channels, [reg.dtype], data_arr)
    servo.disturbance_enable()

    assert np.array_equal(server._disturbance.channels_data[0], data_arr)


@pytest.mark.no_connection
def test_virtual_motor_enable_disable(virtual_drive):
    _, servo = virtual_drive

    assert servo.get_state() == SERVO_STATE.RDY
    servo.enable()
    assert servo.get_state() == SERVO_STATE.ENABLED
    servo.disable()
    assert servo.get_state() == SERVO_STATE.DISABLED


@pytest.mark.no_connection
@pytest.mark.parametrize(
    "plant_name,dist_reg,monit_regs,op_mode",
    [
        (
            "_plant_open_loop_rl_d",
            "CL_VOL_D_SET_POINT",
            ["CL_VOL_D_CMD", "CL_CUR_D_VALUE"],
            OperationMode.VOLTAGE,
        ),
        (
            "_plant_open_loop_rl_q",
            "CL_VOL_Q_SET_POINT",
            ["CL_VOL_Q_CMD", "CL_CUR_Q_VALUE"],
            OperationMode.VOLTAGE,
        ),
        (
            "_plant_open_loop_vol_to_curr_a",
            "CL_VOL_D_SET_POINT",
            ["CL_VOL_D_REF_VALUE", "FBK_CUR_A_VALUE"],
            OperationMode.VOLTAGE,
        ),
        (
            "_plant_open_loop_vol_to_curr_b",
            "CL_VOL_D_SET_POINT",
            ["CL_VOL_D_REF_VALUE", "FBK_CUR_B_VALUE"],
            OperationMode.VOLTAGE,
        ),
        (
            "_plant_open_loop_vol_to_curr_c",
            "CL_VOL_D_SET_POINT",
            ["CL_VOL_D_REF_VALUE", "FBK_CUR_C_VALUE"],
            OperationMode.VOLTAGE,
        ),
        (
            "_plant_closed_loop_rl_d",
            "CL_CUR_D_SET_POINT",
            ["CL_CUR_D_REF_VALUE", "CL_CUR_D_VALUE"],
            OperationMode.CURRENT,
        ),
    ],
)
def test_plants(virtual_drive, plant_name, dist_reg, monit_regs, op_mode):
    server, servo = virtual_drive

    dist_data = [1] + [0] * (MONITORING_NUM_SAMPLES - 1)

    servo.write("DRV_OP_CMD", op_mode, subnode=1)
    create_monitoring_disturbance(servo, dist_reg, monit_regs, dist_data)

    servo.monitoring_enable()
    servo.monitoring_read_data()

    command = servo.monitoring_channel_data(0)
    value = servo.monitoring_channel_data(1)

    value_fft = np.fft.fft(value)
    input_fft = np.fft.fft(dist_data)
    plant = getattr(server, plant_name).plant
    _, freq_response = signal.freqz(
        plant.num,
        plant.den,
        worN=len(value),
        whole=True,
    )
    freq_response_est = value_fft / input_fft

    servo.monitoring_disable()

    assert np.allclose(command, dist_data)
    assert np.allclose(
        np.abs(freq_response), np.abs(freq_response_est), atol=np.amax(np.abs(freq_response)) / 2
    )


@pytest.mark.skip
def test_phasing():
    pass


@pytest.mark.skip
def test_feedbacks():
    pass

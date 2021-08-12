from ingenialink.ipb.servo import IPBServo

import ingenialogger
logger = ingenialogger.get_logger(__name__)


class EthercatServo(IPBServo):
    """Servo object for all the EtherCAT slave functionalities.

    Args:
        net (IPBNetwork): IPB Network associated with the servo.
        target (str): Target ID for the slave.
        dictionary_path (str): Path to the dictionary.
    """
    def __init__(self, net, target, dictionary_path):
        super(EthercatServo, self).__init__(net, target, dictionary_path)
        pass

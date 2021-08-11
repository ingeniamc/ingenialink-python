from ..ipb_servo import IPBServo

import ingenialogger
logger = ingenialogger.get_logger(__name__)


class EthercatServo(IPBServo):
    def __init__(self, net, target, dictionary_path):
        super(EthercatServo, self).__init__(net, target, dictionary_path)
        pass

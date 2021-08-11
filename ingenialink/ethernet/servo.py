from ..ipb_servo import IPBServo


import ingenialogger
logger = ingenialogger.get_logger(__name__)


class EthernetServo(IPBServo):
    def __init__(self, net, target, dictionary_path, port, communication_protocol):
        super(EthernetServo, self).__init__(net, target, dictionary_path)
        self.__port = port
        self.__communication_protocol = communication_protocol

    @property
    def port(self):
        return self.__port

    @port.setter
    def port(self, value):
        self.__port = value

    @property
    def communication_protocol(self):
        return self.__communication_protocol

    @communication_protocol.setter
    def communication_protocol(self, value):
        self.__communication_protocol = value

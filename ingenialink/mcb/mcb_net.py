from ..net import Network


class MCBNetwork(Network):
    def __init__(self, port=None, timeout_rd=0.5, timeout_wr=0.5):
        self.__port = port
        self.__timeout_rd = timeout_rd
        self.__timeout_wr = timeout_wr

    def load_firmware(self, fw_file):
        # TODO: Implement FTP fw loader
        raise NotImplementedError

    def scan_nodes(self):
        raise NotImplementedError

    def connect(self):
        raise NotImplementedError

    def disconnect(self):
        raise NotImplementedError

    def restore_parameters(self):
        raise NotImplementedError

    def store_parameters(self):
        raise NotImplementedError

    def load_configuration(self):
        raise NotImplementedError

    @property
    def port(self):
        return self.__port

    @port.setter
    def port(self, value):
        self.__port = value

    @property
    def timeout_rd(self):
        return self.__timeout_rd

    @timeout_rd.setter
    def timeout_rd(self, value):
        self.__timeout_rd = value

    @property
    def timeout_wr(self):
        return self.__timeout_wr

    @timeout_wr.setter
    def timeout_wr(self, value):
        self.__timeout_wr = value
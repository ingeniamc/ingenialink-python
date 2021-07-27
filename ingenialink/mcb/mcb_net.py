from ..net import Network


class MCBNetwork(Network):
    def __init__(self, port=None, timeout_rd=0.5, timeout_wr=0.5):
        self.__port = port
        self.__timeout_rd = timeout_rd
        self.__timeout_wr = timeout_wr

    # Properties
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
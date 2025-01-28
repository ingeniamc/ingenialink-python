from .signals import Signal


class Environment:
    """Contains the physical values of connected, imposed or observed to the drive."""

    def __init__(self) -> None:
        self.gpi_1_status = Signal[bool](False)
        self.gpi_2_status = Signal[bool](False)
        self.gpi_3_status = Signal[bool](False)
        self.gpi_4_status = Signal[bool](False)

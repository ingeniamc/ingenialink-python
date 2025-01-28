from typing import TYPE_CHECKING

from .signals import Signal

if TYPE_CHECKING:
    from .environment import Environment


class Gpios:
    """General Purpose Input and Outputs."""

    def __init__(self, environment: "Environment"):
        self.value = Signal[int](0)
        self.polarity = Signal[int](0)

        self.__environment = environment

        # Update the inputs value whenever the pin state changes or polarity register changes
        environment.gpi_1_status.watch(self.__update_gpi_status)
        environment.gpi_2_status.watch(self.__update_gpi_status)
        environment.gpi_3_status.watch(self.__update_gpi_status)
        environment.gpi_4_status.watch(self.__update_gpi_status)
        self.polarity.watch(self.__update_gpi_status)

    def __update_gpi_status(self) -> None:
        gpi_status = (
            (int(self.__environment.gpi_1_status.get()) << 0)
            + (int(self.__environment.gpi_2_status.get()) << 1)
            + (int(self.__environment.gpi_3_status.get()) << 2)
            + (int(self.__environment.gpi_4_status.get()) << 3)
        )

        self.value.set(self.polarity.get() ^ gpi_status)

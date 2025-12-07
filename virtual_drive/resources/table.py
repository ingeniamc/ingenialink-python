from virtual_drive.signals import Signal


class VTable:
    """A table that holds values that can be accessed and modified via index and value signals."""

    def __init__(self, depth: int):
        self.__values = [0] * depth

        self.index = Signal[int](0)
        self.value = Signal[int](0)

        self.index.watch(self.__index_changed)
        self.value.watch(self.__value_changed)

    def __index_changed(self) -> None:
        self.value.set(self.__values[self.index.get()])

    def __value_changed(self) -> None:
        current_index = self.index.get()

        if current_index > len(self.__values):
            return

        self.__values[current_index] = self.value.get()

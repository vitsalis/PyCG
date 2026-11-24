from enum import Enum, member


def add(a, b):
    return a + b


def subtract(a, b):
    return a - b


class Operation(Enum):
    ADD = member(add)
    SUBTRACT = member(subtract)

    def apply(self, a, b):
        return self.value(a, b)


Operation.ADD.apply(1, 2)

from enum import Enum, auto


class Color(Enum):
    @staticmethod
    def _generate_next_value_(name, start, count, last_values):
        return name.lower()

    RED = auto()
    GREEN = auto()

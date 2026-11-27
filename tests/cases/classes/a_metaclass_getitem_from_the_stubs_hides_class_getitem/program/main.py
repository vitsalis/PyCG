
import enum
class Color(enum.Enum):
    RED = 1
    def __class_getitem__(cls, key): return cls
Color["RED"]

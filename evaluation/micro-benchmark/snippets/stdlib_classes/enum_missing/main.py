from enum import Enum


class Status(Enum):
    ACTIVE = "active"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN


def parse_known():
    return Status("active")


def parse_unknown():
    return Status("deleted")


parse_known()
parse_unknown()

from typing import get_type_hints


def make_type():
    return int


def scale(value: "make_type()") -> int:
    return value


get_type_hints(scale)

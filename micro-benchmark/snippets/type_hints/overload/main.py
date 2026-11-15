from typing import overload


def convert(value):
    return value


@overload
def parse(value: int) -> int: ...


@overload
def parse(value: str) -> str: ...


def parse(value):
    return convert(value)


parse(1)

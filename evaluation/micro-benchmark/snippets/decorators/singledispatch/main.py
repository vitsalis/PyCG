import functools


@functools.singledispatch
def describe(value):
    pass


@describe.register
def describe_int(value: int):
    pass


@describe.register
def describe_str(value: str):
    pass


describe(1)
describe(1.5)

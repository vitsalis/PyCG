def make_type():
    return int


def scale(value: make_type()) -> int:
    return value


def inspect_scale():
    return scale.__annotations__


inspect_scale()

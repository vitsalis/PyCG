def is_empty():
    return False


def describe():
    return "not empty"


try:
    assert is_empty(), describe()
except AssertionError:
    pass

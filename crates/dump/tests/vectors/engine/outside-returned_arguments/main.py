from functools import update_wrapper, wraps
from typing import cast


def target():
    pass


def other():
    pass


def decorator(function):
    @wraps(function)
    def wrapper():
        return function()

    return wrapper


casted = cast(int, target)
casted()
wrapped = decorator(target)
wrapped()
updated = update_wrapper(other, target)
updated()

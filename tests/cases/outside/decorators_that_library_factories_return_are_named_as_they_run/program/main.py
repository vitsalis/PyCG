
import dataclasses
import functools
@dataclasses.dataclass(frozen=True)
class Point:
    x: int = 0
@dataclasses.dataclass
class Plain:
    y: int = 0
def logged(func):
    @functools.wraps(func)
    def wrapper(*args):
        return func(*args)
    return wrapper

from typing import Generic, TypeVar

T = TypeVar("T")


class Box(Generic[T]):
    def __init__(self):
        pass

    def get(self):
        pass


box = Box[int]()
box.get()

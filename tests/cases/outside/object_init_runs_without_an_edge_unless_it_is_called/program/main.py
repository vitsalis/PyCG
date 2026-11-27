
import abc
class Event(abc.ABC):
    pass
class Request(Event):
    def __init__(self):
        super().__init__()
class Error(Exception):
    pass
def make():
    Event()
    Request()
    Error("x")


import abc
class Base(abc.ABC):
    def __new__(cls):
        return super().__new__(cls)
    def __init__(self): pass
    @abc.abstractmethod
    def run(self): pass
Base()

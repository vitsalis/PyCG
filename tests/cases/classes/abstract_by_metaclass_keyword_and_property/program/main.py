
from abc import ABCMeta, abstractmethod
class Base(metaclass=ABCMeta):
    def __init__(self): pass
    @property
    @abstractmethod
    def size(self): pass
Base()

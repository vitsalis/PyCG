
from abc import ABC, abstractmethod
class Maker(ABC):
    @classmethod
    @abstractmethod
    def make(cls): pass
    def __init__(self): pass
class Helper(ABC):
    @staticmethod
    @abstractmethod
    def help(): pass
    def __init__(self): pass
Maker()
Helper()

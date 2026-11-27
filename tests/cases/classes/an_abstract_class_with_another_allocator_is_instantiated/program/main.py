
from abc import ABC, abstractmethod
class Items(list, ABC):
    @abstractmethod
    def f(self): pass
    def __init__(self): pass
Items()

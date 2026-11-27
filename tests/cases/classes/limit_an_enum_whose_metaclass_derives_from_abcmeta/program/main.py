
from enum import Enum, EnumMeta
from abc import ABCMeta, abstractmethod
class Meta(EnumMeta, ABCMeta): pass
class C(Enum, metaclass=Meta):
    X = 1
    @abstractmethod
    def f(self): pass
    def __init__(self, value): pass
def use():
    C(1)
use()

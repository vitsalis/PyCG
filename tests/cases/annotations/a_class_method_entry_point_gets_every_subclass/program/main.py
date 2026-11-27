
from abc import ABC, abstractmethod
class Base(ABC):
    @classmethod
    def make(cls):
        cls.build()
    @classmethod
    def build(cls): pass
class Child(Base):
    @abstractmethod
    def required(self): pass
    @classmethod
    def build(cls): pass

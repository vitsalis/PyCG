
import abc
from abc import abstractmethod
class Base(abc.ABC):
    def run(self):
        self.step()
    @abc.abstractmethod
    def step(self): pass
class Other(abc.ABC):
    def run(self):
        self.step()
    @abstractmethod
    def step(self): pass
class Child(Base):
    def step(self): pass

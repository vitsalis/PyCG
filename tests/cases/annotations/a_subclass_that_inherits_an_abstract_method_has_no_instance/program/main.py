
import abc
class Base(abc.ABC):
    def run(self):
        self.step()
    @abc.abstractmethod
    def step(self): pass
class Middle(Base):
    pass


from abc import ABC, abstractmethod
class C(ABC):
    @abstractmethod
    def f(self): pass
    def run(self):
        self.f()
    snapshot = locals()

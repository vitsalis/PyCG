
from abc import abstractmethod
class C:
    @abstractmethod
    def f(self): pass
    def run(self):
        self.f()
    snapshot = locals()

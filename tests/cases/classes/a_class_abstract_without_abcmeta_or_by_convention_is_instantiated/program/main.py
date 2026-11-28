
from abc import abstractmethod
class Plain:
    def __init__(self): pass
    def run(self):
        self.step()
    @abstractmethod
    def step(self): pass
class Conventional:
    def __init__(self): pass
    def step(self):
        raise NotImplementedError
class Lone:
    def run(self):
        self.step()
    @abstractmethod
    def step(self): pass
Plain()
Conventional()

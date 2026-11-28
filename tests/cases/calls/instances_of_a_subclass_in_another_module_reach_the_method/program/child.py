
from base import Base
class Child(Base):
    def step(self): pass
def make():
    return Child()

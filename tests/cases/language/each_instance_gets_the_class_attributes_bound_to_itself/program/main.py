
import pathlib
class Base:
    def speak(self): return self
    @staticmethod
    def plain(): pass
    @classmethod
    def make(cls): return cls
    def __getattr__(self, name): return self
class Dog(Base):
    pass
class Place(pathlib.PurePosixPath):
    pass
def talk(animal):
    animal.plain()
    animal.make()
    animal.missing
    return animal.speak()
first = talk(Dog())
second = talk(Dog())
here = Place("a").with_name("b")
there = Place("c").with_name("d")

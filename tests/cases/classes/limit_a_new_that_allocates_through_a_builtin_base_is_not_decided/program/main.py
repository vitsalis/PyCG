
class Base(str):
    def __new__(cls, value):
        return super().__new__(cls, value)
class Loud(Base):
    def __getattr__(self, name): pass
class Quiet(Base):
    def speak(self): pass
Loud("a")
Quiet("b").speak()


class Base:
    def speak(self): return self
    @property
    def size(self): return self
class Dog(Base):
    def speak(self):
        return super().speak()
def early(animal):
    return animal.speak
def measure(animal):
    return animal.size
first, second = Dog(), Dog()
a = early(first)
b = early(second)
a()
def late(animal):
    return animal.speak
c = late(first)
d = measure(first)
e = measure(second)

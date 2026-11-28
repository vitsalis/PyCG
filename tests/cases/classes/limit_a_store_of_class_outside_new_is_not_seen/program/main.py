
class Base:
    def __new__(cls):
        instance = super().__new__(cls)
        retag(instance)
        return instance
    def speak(self): pass
class Other:
    def speak(self): pass
def retag(obj):
    obj.__class__ = Other
Base().speak()

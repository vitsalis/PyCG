
import ext
def f(): pass
def g(): pass

class Registry:
    def __init__(self):
        pass
    def __class_getitem__(cls, key):
        cls.lookup(key)
        return f
    @classmethod
    def lookup(cls, key):
        pass
class Audio(Registry):
    @classmethod
    def lookup(cls, key):
        pass
class Plain:
    pass
def use():
    Audio["mp3"]()
    Plain[0]
    Registry[1:2]

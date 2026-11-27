
import ext
def f(): pass
def g(): pass

class Hooks:
    def __init__(self):
        pass
    def __call__(self):
        pass
    def __init_subclass__(cls):
        cls()
    def __class_getitem__(cls, key):
        cls()

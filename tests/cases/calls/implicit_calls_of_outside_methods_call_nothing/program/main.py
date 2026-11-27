
import lib
class Registry(lib.Registry):
    pass
class Signal(lib.Signal):
    pass
def handler(): pass
def listener(): pass
def use():
    registry = Registry()
    registry["x"] = handler
    Signal() + listener

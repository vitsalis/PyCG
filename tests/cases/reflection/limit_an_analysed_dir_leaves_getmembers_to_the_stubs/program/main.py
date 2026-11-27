
import inspect
class C:
    def hidden(self): pass
    def __dir__(self): return ["shown"]
    def shown(self): pass
class Meta(type):
    def __dir__(cls): return []
class K(metaclass=Meta):
    def hidden(self): pass
class Plain:
    def listed(self): pass
def of_an_instance():
    for name, value in inspect.getmembers(C()):
        value()
def of_a_class():
    for name, value in inspect.getmembers(K):
        value(K())
def control():
    for name, value in inspect.getmembers(Plain()):
        value()
of_an_instance()
of_a_class()
control()

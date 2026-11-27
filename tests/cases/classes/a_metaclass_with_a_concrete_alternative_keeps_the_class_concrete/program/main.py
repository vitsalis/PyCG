
import abc, sys
class PlainMeta(type): pass
class AbstractMeta(abc.ABCMeta): pass
class Meta(PlainMeta if sys.argv else AbstractMeta): pass
class C(metaclass=Meta):
    @abc.abstractmethod
    def f(self): pass
    def __init__(self): pass
C()

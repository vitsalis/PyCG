
import inspect
class C:
    @staticmethod
    def static(): pass
    @classmethod
    def klass(cls): pass
def from_dict():
    C.__dict__["static"]()
    C.__dict__["klass"]()
def members():
    for name, member in inspect.getmembers(C):
        member()
from_dict()
members()

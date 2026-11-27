
class Needle:
    def __eq__(self, other): return False
class Answers(type):
    def __contains__(cls, value): return False
class Iterates(type):
    def __iter__(cls): return iter([1])
class Asked(metaclass=Answers): pass
class Searched(metaclass=Iterates): pass
def asked():
    Needle() in Asked
def searched():
    Needle() in Searched

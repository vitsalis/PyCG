
class M(type):
    def ping(cls): pass
class K(metaclass=M):
    pass
object.__new__(M).ping()


import sys
class M1(type): pass
class M2(type): pass
class A(metaclass=M1 if sys.argv else M2):
    def __class_getitem__(cls, key): return cls
A[int]

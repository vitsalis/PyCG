
import types
class A(metaclass=types.new_class):
    def __class_getitem__(cls, key): return cls
A[int]

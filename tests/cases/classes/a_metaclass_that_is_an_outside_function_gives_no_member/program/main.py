
import types
class C(metaclass=types.new_class):
    def __class_getitem__(cls, key): pass
C[0]
C.missing()

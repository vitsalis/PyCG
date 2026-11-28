
import abc
class BaseMeta(type): pass
class SubMeta(BaseMeta): pass
class A(metaclass=BaseMeta): pass
class B(A, metaclass=SubMeta): pass
class C(B, metaclass=BaseMeta): pass
class D(A): pass
class Plain: pass
class Abstract(abc.ABC): pass

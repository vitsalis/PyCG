
class A:
    @classmethod
    def create(cls):
        return cls()
class B(A):
    def __init__(self): pass
    @classmethod
    def create(cls):
        return super().create()
B.create()

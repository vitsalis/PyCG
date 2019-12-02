class A:
    def __init__(self):
        pass

class C(B):
    def __init__(self):
        super().__init__()

class B(A):
    def __init__(self):
        super().__init__()

c = C()

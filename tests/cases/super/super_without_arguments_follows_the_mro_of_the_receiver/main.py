
class A:
    def run(self): pass
class B(A):
    def run(self):
        super().run()
class C(A):
    def run(self):
        super().run()
class D(B, C):
    pass
D().run()

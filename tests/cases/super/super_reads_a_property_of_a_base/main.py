
def f(): pass
class A:
    @property
    def handler(self):
        return f
class B(A):
    @property
    def handler(self):
        return super().handler
B().handler()

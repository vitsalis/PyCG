
class A:
    def one(self): pass
    def two(self): pass
def run():
    for name in vars(A):
        getattr(A(), name)()
run()


class A:
    pass
def run():
    for member in vars(A).values():
        member(A())
def extra(self): pass
A.extra = extra
run()

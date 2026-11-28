
class A:
    def _f_one(self): pass
    def _f_two(self): pass
def run():
    for name, member in A.__dict__.items():
        member(A())
run()

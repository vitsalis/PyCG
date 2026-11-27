
class X:
    def __repr__(self): return "x"
def run():
    str([iter([X()])])
run()

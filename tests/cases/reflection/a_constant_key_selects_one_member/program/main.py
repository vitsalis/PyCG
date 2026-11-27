
class C:
    def first(self): pass
    def second(self): pass
def run():
    C.__dict__["first"](C())
run()

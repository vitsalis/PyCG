
class C:
    def m(self): pass
class D:
    def m(self): pass
def first():
    yield C()
def second():
    yield D()
first().__next__().m()
second().throw(ValueError).m()

class C:
    def m(self): pass
s = set()
s.add(C())
s.pop().m()
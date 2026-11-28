class C:
    def __lt__(self, other): return True
a = b = c = C()
a < b < c
if a:
    def f(): a < b
else:
    def f(): b < c

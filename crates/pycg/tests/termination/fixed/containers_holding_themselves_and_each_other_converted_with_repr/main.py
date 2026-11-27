class E:
    def __repr__(self): return ''
a = [E()]
b = {'k': a}
a.append(a)
a.append(b)
for x in (a, b):
    repr(x)
    f'{x}'

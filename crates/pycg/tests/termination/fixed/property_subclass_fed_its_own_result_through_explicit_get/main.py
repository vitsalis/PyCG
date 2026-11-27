class P(property): pass
def read(self):
    return P(read)
p = P(read)
for _ in range(2):
    p = p.__get__(p)
    p = P.__get__(p, p, type(p))
    p = p.getter(p)

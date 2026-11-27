import sys
from typing import TYPE_CHECKING
def f(a, *args, k=None, **kw):
    return a
x = f(1, *[2], None, k=None, **{'z': 3})
y = not x and (x or -5) if x < 3 <= 4 else ~x
z = (lambda p: p)(x) + 2 * x % 3 - x.real
s = f'a{x!r:>{y}}b{z=}' + '%s-%d' % (x, y) + '{0.real} {k}'.format(x, k=y)
u = [x, *s], (x,), {x, *s}, {x: y, **{}}
v = x[1:2], x[::2], x[-1:], x[y], sys.modules['os']
w = (q := f(x)) is None or q in (1, 2) or q not in [3]
if TYPE_CHECKING:
    pass
class C:
    def m(self):
        return super().m(), C.__dict__, vars(C)

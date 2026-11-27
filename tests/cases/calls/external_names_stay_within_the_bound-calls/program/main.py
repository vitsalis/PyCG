
import ext
x = ext.a
while x:
    x = x.b().c[0].d
    for y in x:
        x = y.e
    with x as z:
        x = z.f

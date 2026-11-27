
import ext
def f(): pass
def g(): pass

None.x += f()
None[0] += g()
None.y = f()
None[1] = g()
del None.x
del None[0]

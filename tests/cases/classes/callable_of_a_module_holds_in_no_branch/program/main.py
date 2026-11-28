
import mod
def use():
    m = mod
    if callable(m):
        m.f()
    else:
        m.g()

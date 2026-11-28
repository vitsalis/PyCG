
import ext
def f(): pass
def g(): pass

def use(a, b):
    f"{a}.{b}".rstrip("0")
    f"{a:08b}".zfill(3)
    f"{a}"[:-1].strip()

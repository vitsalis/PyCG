
def fallback(): pass
def supplied(): pass
class Base:
    def __init_subclass__(cls, *, hook=fallback):
        hook()
def make():
    type("C", (Base,), {}, hook=supplied)
def unpacked():
    type(*("C", (Base,), {}))
def partly():
    type("C", (Base,), *())
make()
unpacked()
partly()

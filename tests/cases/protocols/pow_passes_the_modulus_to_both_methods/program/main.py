
def g(): pass
class Mod:
    def __call__(self): g()
class Power:
    def __pow__(self, exp, mod=None):
        mod()
    def __rpow__(self, base, mod=None):
        mod()
pow(Power(), 2, Mod())
pow(2, Power(), Mod())

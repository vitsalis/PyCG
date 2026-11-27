
def f(): pass
class Power:
    def __pow__(self, exp, mod=None):
        return self
    def __rpow__(self, base, mod=None):
        return f
    def run(self): pass

def two(a):
    pow(a, 2).run()
    pow(2, a)()
def three(a):
    pow(a, 2, 5).run()
    pow(2, a, 5)()
def keywords(a):
    pow(2, exp=a, mod=5)()
two(Power())
three(Power())
keywords(Power())

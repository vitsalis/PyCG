
def f(): pass
def g(): pass
class Lazy:
    def __getattr__(self, name):
        return f
class Eager:
    def __getattr__(self, name):
        return g
def use(x):
    return x.missing
def call(x):
    use(x)()
for x in (Lazy(), Lazy(), Eager(), Eager()):
    call(x)

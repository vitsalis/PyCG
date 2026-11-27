def f(): pass
def g(): pass
def h(): pass

class A:
    def run(self): pass
    def stop(self): pass
def take(**kwargs):
    for name in kwargs:
        getattr(A(), name)()
def forward(mapping):
    take(**mapping)
def i1(x): return x
def i2(x): return i1(x)
def i3(x): return i2(x)
forward({"run": 1})
forward(i3(i3({"stop": 1})))

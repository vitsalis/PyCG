
class A:
    def __eq__(self, other): return True
    def __lt__(self, other): return True
    def __contains__(self, value): return True
    def __iter__(self): return iter([])
    def __getitem__(self, key): return key
    def __setitem__(self, key, value): pass
    def __delitem__(self, key): pass
    def __bool__(self): return True
    def __len__(self): return 0
    def __format__(self, spec): return ""
    def __str__(self): return ""
    def __repr__(self): return ""
    def __hash__(self): return 0
    def __add__(self, other): return self
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def __call__(self): pass
    def __await__(self): yield
    def __get__(self, obj, owner): return self
    def __set__(self, obj, value): pass
    def method(self): pass
class B(A): pass
class C(A): pass
def instances():
    for value in (A(), B(), C()):
        use(value)
def classes():
    for value in (A, B, C):
        use(value)
def f(): pass
def g(): pass
def h(): pass
for exported in (f, g, h):
    pass

class Lazy:
    def __getattr__(self, name): return name
def use(value):
    class Derived(value, Lazy): pass
    Derived().method(); Derived.method; str(Derived())
    class Other(value): pass
    Other().missing; super(Other, Other()).method()
classes()

class Meta(type):
    def __call__(cls): pass
    def __getitem__(cls, key): pass
    def describe(cls): pass
class M2(Meta): pass
class M3(Meta): pass
def use(meta):
    class Made(metaclass=meta):
        def __init__(self): pass
    Made(); Made[0]; Made.describe()
for meta in (Meta, M2, M3):
    use(meta)

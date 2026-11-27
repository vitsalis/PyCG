
import inspect
class A:
    def base(self): pass
class B(A):
    def own(self): pass
def own_namespace():
    for name, member in B.__dict__.items():
        member(B())
def members():
    for name, member in inspect.getmembers(B):
        member(B())
own_namespace()
members()

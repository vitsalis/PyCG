
import ext
def first(): pass
def second(): pass
class C:
    a = first
    b = second
    selector = "b"
key = "selector"
name = "a" if ext.flag else getattr(C, key)
getattr(C, name)()

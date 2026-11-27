
class Holder: pass
class A: pass
class Last: pass
holder = Holder()
for base in (int, str, list, tuple, dict, set, bytes, Exception, A):
    holder.base = base
class C(holder.base): pass
getattr(C(), "missing", None)
name = "base"
setattr(holder, name, Last)

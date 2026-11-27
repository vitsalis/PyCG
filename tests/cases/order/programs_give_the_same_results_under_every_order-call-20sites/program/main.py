
import lib
class Lock:
    def __enter__(self): pass
    def __exit__(self, *args): pass
    def __iter__(self): return iter([])
    def __format__(self, spec): return ""
    @property
    def p(self): pass
def make(): return Lock()
def run(callback, name):
    with make() as lock:
        for x in make():
            callback(x)
    getattr(lock, name)()
    lib.a.b.c()
    return lock.p, f"{lock}", [y for y in list(Lock())]

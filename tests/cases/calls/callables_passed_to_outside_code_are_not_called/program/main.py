
import ext
def f(): pass
def g(): pass
class C:
    def m(self):
        self.helper()
    def helper(self): pass
    def __call__(self): pass
def run():
    ext.register(f)
    ext.schedule(1, callback=C().m)
    ext.watch(C())
    ext.later(lambda: g())

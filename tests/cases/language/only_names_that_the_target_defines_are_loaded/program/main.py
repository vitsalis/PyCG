
import ext
class Proxy:
    def __getattr__(self, name):
        return ext.lookup(name)
class Remote(ext.Base):
    def visit_local(self): pass
class Visitor:
    def visit_field(self): pass
def dispatch(kind):
    getattr(Proxy(), "visit_" + kind)()
    getattr(Remote(), "visit_" + kind)()

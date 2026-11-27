
import ext
def hit(): pass
class C: pass
c = C()
c.visit_a = hit
getattr(c, "visit_" + ext.value)()

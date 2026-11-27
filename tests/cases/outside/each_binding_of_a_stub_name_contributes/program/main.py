
import other
class C:
    def local(self): pass
def use(x):
    x.local()
    x.foreign()

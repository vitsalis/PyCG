
import ext
class Base:
    def run(self): pass
def pick(x):
    s = super(Base, x)
pick(ext.make())
pick("text")

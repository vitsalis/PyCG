
import ext
class Base:
    def run(self): pass
def pick(x):
    super(Base, x).run()
pick(ext.make())
pick("text")

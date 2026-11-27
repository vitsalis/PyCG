
class Base:
    def run(self): pass
def base():
    return Base
class Late(base()):
    def run(self):
        s = super(Base, self)
Late().run()

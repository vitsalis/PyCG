
class Root:
    def run(self): pass
class Base(Root):
    def run(self): pass
def base():
    return Base
class Child(Base):
    def run(self): pass
class Late(base()):
    def run(self):
        super(Base, self).run()
Late().run()


class Root:
    def run(self): pass
class Base(Root):
    def run(self): pass
class Child(Base):
    def run(self): pass
class Other(Root):
    def run(self): pass
def pick(x):
    super(Base, x).run()
for x in (Base(), Child(), Other(), Base, Child, Other):
    pick(x)

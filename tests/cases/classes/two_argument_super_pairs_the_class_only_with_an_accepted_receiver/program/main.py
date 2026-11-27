
class Base:
    def run(self): pass
class Child(Base):
    def run(self): pass
class Other:
    def run(self): pass
def pick(x):
    s = super(Base, x)
for x in (Base(), Child(), Other(), Base, Child, Other):
    pick(x)

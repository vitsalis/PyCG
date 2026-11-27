
class Root:
    def run(self): pass
class Base(Root):
    def run(self):
        super().run()
class Other(Root):
    def run(self): pass
class Sub(Other, Base):
    pass
Base.run(Other())
Base.run(Sub())

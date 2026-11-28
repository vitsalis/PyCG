
class Base:
    def handler(self): pass
    def run(self):
        self.handler()
class Child(Base):
    def handler(self): pass
Child().run()

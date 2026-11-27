
class Base:
    pass
def each():
    for cls in Base.__subclasses__():
        cls().run()
each()
class Late(Base):
    def run(self): pass

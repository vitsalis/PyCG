
class Left:
    pass
class Right:
    pass
def pick(flag):
    return Left if flag else Right
class C(pick(input())):
    def run(self): pass
def each():
    for cls in Left.__subclasses__():
        cls().run()
each()

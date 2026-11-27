
class Other:
    def run(self): pass
C = Other
def use(x, later, inner):
    x.run()
    later.run()
    inner.run()
class Later:
    def run(self): pass
class Outer:
    class Inner:
        def run(self): pass


class Outer:
    class Inner:
        def run(self): pass
    def use(self, inner):
        inner.run()


class C:
    global T
    class T:
        def run(self): pass
    def use(self, x):
        x.run()
def use(x):
    x.run()

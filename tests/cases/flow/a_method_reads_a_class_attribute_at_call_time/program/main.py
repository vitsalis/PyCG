
def f(): pass
def g(): pass
def h(): pass

class C:
    handler = f
    def run(self):
        self.handler()
        C.handler()
C.handler = g
C().run()

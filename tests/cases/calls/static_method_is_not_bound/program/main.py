
class C:
    @staticmethod
    def s(callback):
        callback()
    def m(self):
        self.s(g)
def g(): pass
C().s(g)
C.s(g)

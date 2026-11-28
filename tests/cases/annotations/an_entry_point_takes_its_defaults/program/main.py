
def g(): pass
def api(cb=g, *, key=g):
    cb()
    key()
class Service:
    def run(self, cb=g):
        cb()

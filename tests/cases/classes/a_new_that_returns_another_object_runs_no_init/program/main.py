
import ext
def f(): pass
def g(): pass

class Real:
    def __init__(self):
        pass
    def run(self):
        pass
class Proxy:
    def __new__(cls):
        return Real()
    def __init__(self):
        pass
Proxy().run()

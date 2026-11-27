
class Other:
    def m(self): pass
class Factory:
    def __new__(cls): return Other()
class Made(Factory):
    locals()
Made().m()

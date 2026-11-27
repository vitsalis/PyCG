
class C(list):
    def __iter__(self):
        return super().__iter__()
    def ping(self): pass
class Abstract:
    def run(self): pass
def use(a: Abstract):
    a.run()

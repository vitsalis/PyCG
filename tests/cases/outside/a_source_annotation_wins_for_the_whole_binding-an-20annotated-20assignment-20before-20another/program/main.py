class Wrong:
    def ping(self): pass
flag = input()
x: object = None
x = None
x.ping()
class C:
    x: object = None
    x = None
    def go(self):
        self.x.ping()

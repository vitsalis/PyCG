class Wrong:
    def ping(self): pass
flag = input()
x = None
x: object
x.ping()
class C:
    x = None
    x: object
    def go(self):
        self.x.ping()

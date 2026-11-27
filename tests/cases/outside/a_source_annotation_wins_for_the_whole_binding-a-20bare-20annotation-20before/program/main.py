class Wrong:
    def ping(self): pass
flag = input()
x: object
x = None
x.ping()
class C:
    x: object
    x = None
    def go(self):
        self.x.ping()

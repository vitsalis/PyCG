class Wrong:
    def ping(self): pass
flag = input()
if flag:
    x: object = None
else:
    x = None
x.ping()
class C:
    if flag:
        x: object = None
    else:
        x = None
    def go(self):
        self.x.ping()

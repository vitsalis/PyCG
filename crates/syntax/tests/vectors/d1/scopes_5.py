
x = 0
def outer():
    y = 0
    class C:
        x = 1
        y = 1
        z = x
        def m(self):
            return x, y

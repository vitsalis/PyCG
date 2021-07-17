class Cls:
    x = "b"
    def func(self, d):
        d[self.x]

d = {"a": "ab"}

cl = Cls()
cl.func(d)

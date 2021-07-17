class Cls:
    def func(self):
        return "b"

d = {"a": "ab"}

cl = Cls()
d[cl.func()]

class Cls:
    x = "a"

d = {"a": "ab"}

cl = Cls()
cl.x = "b"
d[cl.x]

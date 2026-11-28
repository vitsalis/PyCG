def f(): pass
class C:
    x = f()
ys = [f() for _ in range(2)]

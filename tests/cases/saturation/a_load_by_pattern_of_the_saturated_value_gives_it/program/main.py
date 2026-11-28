
class A:
    def visit_x(self): pass
class B(A): pass
class C(A): pass
def use(value, name):
    getattr(value, f"visit_{name}")()
for value in (A(), B(), C()):
    use(value, "x")

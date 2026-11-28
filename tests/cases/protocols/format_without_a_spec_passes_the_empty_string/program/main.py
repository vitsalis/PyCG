
class A:
    def __format__(self, spec):
        return spec.upper()
class B:
    def __format__(self, spec):
        return spec.lower()
format(A())
f"{B()}"

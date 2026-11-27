class Shown:
    def __str__(self):
        return "shown"

    def __repr__(self):
        return "Shown()"

    def __format__(self, spec):
        return spec


class Number:
    def __pow__(self, other, modulo=None):
        return self

    def __rpow__(self, other):
        return self


text = str(Shown())
code = repr(Shown())
formatted = format(Shown(), ">4")
power = pow(Number(), 2)
modular = pow(Number(), 2, 5)
reflected = pow(2, Number())

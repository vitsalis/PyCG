import functools
import operator


class Vector:
    def __add__(self, other):
        return self

    def __getitem__(self, index):
        return 0


v = Vector()
operator.add(v, v)
operator.getitem(v, 0)
functools.reduce(operator.add, [v, v])

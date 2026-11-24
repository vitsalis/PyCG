import math

class Measure:
    def __trunc__(self):
        return 1

try:
    int(Measure())
except TypeError:
    pass
math.trunc(Measure())

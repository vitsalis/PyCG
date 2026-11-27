
import math
import somelib
import time
class Stored(time.struct_time):
    def __iter__(self): return iter([])
class Unknown(somelib.Base):
    def __iter__(self): return iter([])
def stored(point):
    math.dist(point, point)
def unknown(point):
    math.dist(point, point)
stored(Stored())
unknown(Unknown())

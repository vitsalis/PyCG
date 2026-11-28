
class Tested:
    def __bool__(self): return True
class Untested:
    def __bool__(self): return True
class Low:
    def __lt__(self, other): return Tested()
class High:
    def __lt__(self, other): return Untested()
def chain(a, b, c):
    a < b < c
def condition(a, b, c):
    if a < b < c:
        pass
def contains(a, b, c):
    a < b in c
chain(Low(), High(), High())
condition(Low(), High(), High())
contains(Low(), High(), [1])

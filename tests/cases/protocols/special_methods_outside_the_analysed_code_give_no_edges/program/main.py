
class Mapping(dict):
    pass
def use(m):
    m["a"] = 1
    m["a"] + 1
    str(m)
use(Mapping())


class Plain:
    def __init__(self): pass
class Made:
    def __new__(cls): return super().__new__(cls)
    def __init__(self): pass
def make(kind):
    return kind()
first = make(Plain)
second = make(Made)
third = Plain()
fourth = Made()

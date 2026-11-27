def deco(f): return f
def factory(): return deco
@deco
def a(): pass
@factory()
def b(): pass

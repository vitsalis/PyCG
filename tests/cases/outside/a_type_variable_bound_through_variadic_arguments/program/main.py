
def a(): pass
def b(): pass
def c(): pass
max(a, b, c, key=lambda f: f.__name__)()


def f():
    pass
def wrapper():
    staticmethod(f).__subclasshook__(int)
def pattern(x):
    f"a{x}".__subclasshook__(int)

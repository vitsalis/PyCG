class A(Exception):
    def __init__(self):
        pass

a = A
try:
    raise a
except A:
    pass

class A(Exception):
    def __init__(self):
        pass

try:
    raise A
except A:
    pass

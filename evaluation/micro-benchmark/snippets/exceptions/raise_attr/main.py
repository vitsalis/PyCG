class A:
    class B(Exception):
        def __init__(self):
            pass

try:
    raise A.B
except A.B:
    pass

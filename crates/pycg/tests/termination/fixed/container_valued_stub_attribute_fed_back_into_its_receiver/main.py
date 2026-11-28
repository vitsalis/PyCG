from types import SimpleNamespace
x = SimpleNamespace()
for _ in (0,):
    x = x.__dict__

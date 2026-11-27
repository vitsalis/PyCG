def f(): pass
def g(): pass
def h(): pass

for x in [f]:
    x()
for key in {g: 1}:
    key()
d = {"a": h}
for name, value in d.items():
    value()
for value in d.values():
    value()

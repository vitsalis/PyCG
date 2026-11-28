classes = (int,)
for _ in range(2):
    classes = (classes,)
x = 's'
if isinstance(x, classes):
    x.upper()
else:
    x.lower()
if issubclass(x, classes):
    x.upper()

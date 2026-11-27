
def a(): pass
def b(): pass
def c(): pass
def run(action, *args):
    action(*args)
xs = []
ys = set()
run(xs.extend, [a])
run(ys.update, [b], [c])
for f in ys:
    f()

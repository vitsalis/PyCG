
def keyword(*, key): pass
def default(*, key=1): pass
def run(f):
    f()
for f in (keyword, default):
    run(f)

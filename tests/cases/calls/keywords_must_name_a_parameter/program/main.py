
def plain(a): pass
def keyword(*, key): pass
def anything(**kwargs): pass
def positional_only(a, /): pass
def run(f):
    f(key=1)
for f in (plain, keyword, anything, positional_only):
    run(f)
def twice(f):
    f(1, a=2)
twice(plain)

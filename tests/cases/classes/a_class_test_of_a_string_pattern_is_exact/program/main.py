
def use(x):
    p = "a%sb" % x
    if not isinstance(p, str):
        p.upper()
def other(x):
    p = "a%sb" % x
    if isinstance(p, str):
        p.lower()


def warn(major, minor, cause, fix): pass
def keyed(*, key): pass
def after(): pass
def missing():
    warn(0, 13, "cause")
    after()
def assigned():
    result = keyed(1)
    after()
def unknown_keyword():
    warn(0, 13, "cause", fix="fix", extra=1)
    after()
def binds():
    warn(0, 13, "cause", fix="fix")
    after()
def unpacked(args):
    warn(*args)
    after()
def nested():
    print(warn(0))
    after()
def guarded():
    try:
        warn(0)
    except TypeError:
        pass
    after()
def decorated_wrapper(f):
    return f
@decorated_wrapper
def decorated(a): pass
def through_decorator():
    decorated()
    after()
def rebound_name():
    twice()
    after()
def twice(a): pass
twice = after
for function in (missing, assigned, unknown_keyword, binds, unpacked,
                 nested, guarded, through_decorator, rebound_name):
    function()

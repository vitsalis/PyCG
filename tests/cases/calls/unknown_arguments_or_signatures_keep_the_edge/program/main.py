
import ext
@ext.register
def decorated(a): pass
def one(a): pass
def run(args, kw):
    decorated()
    one(*args)
    one(**kw)
run((), {})

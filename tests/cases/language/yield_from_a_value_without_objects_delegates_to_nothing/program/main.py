
import ext
def f(): pass
def g(): pass

def take(value): pass
def gen():
    take((yield from 0.5))

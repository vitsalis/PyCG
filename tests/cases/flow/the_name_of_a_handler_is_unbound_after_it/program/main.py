
def f(): pass
def g(): pass
def h(): pass

import ext
class Failure(Exception):
    def __call__(self): pass
def use():
    error = f
    try:
        ext.run()
    except Failure as error:
        pass
    error()
Failure()

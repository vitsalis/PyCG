def f(): pass
def g(): pass
def h(): pass
from keys import FIRST
def call(key='b'):
    table[key]()
table = {'a': f, 'b': g, 'c': h}
table[FIRST]()
call()

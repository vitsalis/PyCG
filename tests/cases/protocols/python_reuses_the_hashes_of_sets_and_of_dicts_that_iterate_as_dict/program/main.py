import collections

class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
items = [Key()]
keys = {Key()}
table = {Key(): 1}
ordered = collections.OrderedDict([(Key(), 1)])
counts = collections.Counter([Key()])
def kept0():
    {*keys}
kept0()
def kept1():
    {*table}
kept1()
def kept2():
    keys.union(table)
kept2()
def kept3():
    collections.Counter(table)
kept3()
def kept4():
    {**counts}
kept4()
def hashed0():
    {*items}
hashed0()
def hashed1():
    {*ordered}
hashed1()
def hashed2():
    set(ordered)
hashed2()
def hashed3():
    set(counts)
hashed3()
def hashed4():
    dict.fromkeys(ordered)
hashed4()
def hashed5():
    {**ordered}
hashed5()
def hashed6():
    dict(ordered)
hashed6()
def hashed7():
    {}.update(ordered)
hashed7()
def hashed8():
    collections.Counter(keys)
hashed8()

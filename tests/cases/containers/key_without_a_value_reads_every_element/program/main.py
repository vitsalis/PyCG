def f(): pass
def g(): pass
def h(): pass

TABLE = [f, g]
def item(i):
    TABLE[i]()
def last():
    TABLE[len(TABLE) - 1]()
def put(i):
    TABLE[i] = h

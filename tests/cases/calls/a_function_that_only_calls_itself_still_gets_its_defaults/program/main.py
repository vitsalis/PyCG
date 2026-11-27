
def g(): pass
def fold(items, combine=g):
    combine()
    if items:
        fold(items[1:], combine=combine)

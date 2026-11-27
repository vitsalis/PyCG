
def h(): pass
def handler(event=None, fallback=h):
    fallback()
list(map(handler, [1]))

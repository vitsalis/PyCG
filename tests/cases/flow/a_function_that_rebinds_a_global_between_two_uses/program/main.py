
def f(): pass
def g(): pass
def h(): pass

handler = f
handler()
def install():
    global handler
    handler = g
install()
handler()


def f(): pass
def g(): pass
def h(): pass

handler = f
def install():
    global handler
    handler = g
handler()
def outer():
    local = f
    def swap():
        nonlocal local
        local = g
    local()

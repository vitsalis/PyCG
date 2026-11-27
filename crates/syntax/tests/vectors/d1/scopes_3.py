
def outer():
    global x
    x = 1
    def inner():
        return x


def outer():
    x = 1
    def middle():
        def inner():
            nonlocal x
            x = 2
        return inner

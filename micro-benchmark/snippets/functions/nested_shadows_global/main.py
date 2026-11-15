def helper():
    pass

def outer():
    def helper():
        pass
    helper()

outer()
helper()

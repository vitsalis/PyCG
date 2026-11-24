def func1():
    pass

def outer(n):
    def countdown(k):
        if k > 0:
            countdown(k - 1)
        else:
            func1()

    countdown(n)

outer(2)

def func1(q, a=1):
    pass


def func2(a=1, /):
    pass


def func3(q, a=1, b=2, /, c=3):
    pass


func1(0)
func2()
func3(0)

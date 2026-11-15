def func1():
    return 1

message = f"{(lambda: func1())()}"

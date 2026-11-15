from collections import defaultdict

def func1():
    pass

handlers = defaultdict(lambda: func1)
handlers["missing"]()

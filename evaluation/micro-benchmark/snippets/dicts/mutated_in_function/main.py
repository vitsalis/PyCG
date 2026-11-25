def func1():
    pass

def register(table):
    table["run"] = func1

handlers = {}
register(handlers)
handlers["run"]()

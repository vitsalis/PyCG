
def on_open(): pass
def on_close(): pass
def other(): pass
def fallback(): pass
def unknown(): pass
TABLE = {"on_open": on_open, "other": other}
def k1(): return k2()
def k2(): return k3()
def k3(): return "on_close"
def fill():
    TABLE[k1()] = on_close
def put(key):
    TABLE[key] = unknown
def dispatch(table, event):
    table["on_%s" % event]()
    table.get(f"{event}_x", fallback)()
def first():
    dispatch(second(), "x")
def second():
    return TABLE
first()

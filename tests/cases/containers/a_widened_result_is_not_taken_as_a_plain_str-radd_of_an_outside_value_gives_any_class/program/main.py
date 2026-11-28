def f(): pass
def g(): pass
def h(): pass

import ext
k = "pre_" + ext.value

table = {"hit": f, "top_x": g}
def read():
    table["top_" + k]()

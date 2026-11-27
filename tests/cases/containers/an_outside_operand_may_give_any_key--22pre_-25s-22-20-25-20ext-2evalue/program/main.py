def f(): pass
def g(): pass
def h(): pass

import ext
table = {"hit": f, "pre_x": g, "other": h}
def read():
    table["pre_%s" % ext.value]()


import ext
def f(): pass
def g(): pass

table = {"pre_a": f, "other": g}
def read(name):
    prefix = "pre_"
    table[prefix + name]()
read("a")


import lib
def job(): pass
def use():
    lib.make(job)()
    lib.make()(job)()

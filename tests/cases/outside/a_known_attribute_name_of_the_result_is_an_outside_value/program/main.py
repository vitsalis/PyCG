import lib
def invoke(name):
    getattr(lib.make(), name)()
def guess(name):
    getattr(lib.make(), name)()
invoke("run")

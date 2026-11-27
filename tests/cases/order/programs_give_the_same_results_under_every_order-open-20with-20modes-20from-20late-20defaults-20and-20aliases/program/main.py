
class C:
    mode = "wb"
    def run(self, mode="rb", size=0):
        open("p", mode, size).close()
        open("p", C.mode).close()
def method():
    return "run"
def uncalled(mode="r+b"):
    open("p", mode).close()
def empty(mode):
    open("p", mode).flush()
getattr(C(), method())()

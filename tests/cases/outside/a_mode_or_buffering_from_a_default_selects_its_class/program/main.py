
class C:
    def run(self, mode="rb"):
        open("p", mode).close()
def method():
    return "run"
# The method is reached only through a computed name, which the
# completion resolves.
getattr(C(), method())()
def uncalled(mode="rb"):
    open("p", mode).close()
def unbuffered(size=0):
    open("p", "rb", size).close()

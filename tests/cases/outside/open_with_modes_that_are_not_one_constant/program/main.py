
def two(mode):
    open("p", mode).close()
def unknown(mode: str):
    open("p", mode).close()
def missing(mode):
    open("p", mode).close()
def buffering(size):
    open("p", "rb", size).close()
def rejected():
    open("p", "rw").close()
    open("p", "w", 0).close()
def unpacked(args):
    open("p", *args).close()
two("r")
two("wb")
unknown("r")
buffering(0)
buffering(4096)
rejected()
unpacked(["r"])


import pathlib
def mode():
    return MODE
def size():
    return SIZE
def nothing(given):
    return open("p", given)
def use():
    open("p", mode()).close()
    with open("p", mode(), size()) as f:
        f.read()
    pathlib.Path("p").open(mode=mode(), buffering=size()).write(b"")
    nothing(NOTHING).close()
MODE = "r"
MODE = "wb"
MODE = "r+b"
MODE = "rw"
SIZE = 0
SIZE = -1
SIZE = int()
use()

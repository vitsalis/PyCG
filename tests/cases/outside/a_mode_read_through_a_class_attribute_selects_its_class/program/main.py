
import enum
class Options:
    mode = "rb"
    size = 0
class Mode(enum.StrEnum):
    WRITE = "wb"
def read():
    open("p", Options.mode).close()
def raw():
    open("p", "wb", Options.size).close()
def write():
    open("p", Mode.WRITE).close()
read()
raw()
write()

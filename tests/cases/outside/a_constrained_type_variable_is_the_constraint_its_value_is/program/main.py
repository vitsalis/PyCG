
import glob
def text():
    glob.escape("x").upper()
def data():
    glob.escape(b"x").lower()
def other():
    glob.escape(bytearray(b"x")).lower()
text()
data()
other()

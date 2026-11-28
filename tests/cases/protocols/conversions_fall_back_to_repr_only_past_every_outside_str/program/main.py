
class Text(str):
    def __repr__(self): return ""
class Data(bytes):
    def __repr__(self): return ""
class Buffer(bytearray):
    def __repr__(self): return ""
class Failure(Exception):
    def __repr__(self): return ""
class Number(int):
    def __repr__(self): return ""
def convert(value):
    str(value)
    f"{value}"
    "{}".format(value)
convert(Text("a"))
convert(Data(b"a"))
convert(Buffer(b"a"))
convert(Failure())
convert(Number(1))

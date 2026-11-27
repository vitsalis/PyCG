
def make(cls):
    cls.from_bytes(b"\x01", "big")
classmethod(make).__get__(None, int)()

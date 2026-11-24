def inner():
    return "x"

def outer(s):
    return s

message = f"{outer(f"{inner()}")}"

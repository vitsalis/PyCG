import contextlib

def cleanup():
    pass

with contextlib.ExitStack() as stack:
    stack.callback(cleanup)

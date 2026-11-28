
import errno
def name(code):
    return errno.__dict__.get(code)

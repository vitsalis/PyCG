
import os
def pick(c):
    return open if c else os.fdopen
pick(1)("p", "rb", 0).close()

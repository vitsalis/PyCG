
import sys
if sys.platform == "win32":
    callable = lambda value: True
len = len
def check(value):
    callable(value)
    len(value)


import sys
from sys import stderr
def report(text, file=sys.stdout):
    file.write(text)
    file.flush()
def read():
    return sys.stdin.readline()
stderr.write("x")
report("y")
read()

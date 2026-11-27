
import functools
import re
def repl(m): pass
def text():
    re.sub("a", "b", "abc")
    re.sub("a", r"\1", "abc", count=1)
def partial():
    re.sub("a", functools.partial(repl), "abc")
def control():
    re.sub("a", repl, "abc")
text()
partial()
control()

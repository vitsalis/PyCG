
import re
def repl(m):
    return m.group(0)
re.sub("a", repl, "abc")

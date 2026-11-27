
import re
def repl(m): pass
def by_keyword(m): pass
def by_pattern(m): pass
def counted(m): pass
def counted_by_pattern(m): pass
def chosen(m): pass
def on_bytes(m): pass
class Replacer:
    def method(self, m): pass
replacer = Replacer()
def use(flag):
    re.sub("a", repl, "abc")
    re.sub("a", lambda m: m, "abc")
    re.sub("a", replacer.method, "abc")
    re.sub("a", repl=by_keyword, string="abc")
    re.compile("a").sub(by_pattern, "abc")
    re.subn("a", counted, "abc")
    re.compile("a").subn(counted_by_pattern, "abc")
    replacement = "x" if flag else chosen
    re.sub("a", replacement, "abc")
    re.sub(b"a", on_bytes, b"abc")
use(True)


import re
class Replacer:
    def method(self, m): return ""
def pick():
    return CHOSEN
def pattern():
    return PATTERN
def use():
    re.sub("a", pick(), "abc")
    pattern().subn(repl=pick(), string="abc")
    re.sub("a", re.sub, "abc")
CHOSEN = "x"
CHOSEN = Replacer().method
CHOSEN = lambda m: m
PATTERN = re.compile("a")
use()

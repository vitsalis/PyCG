
import re
class Options:
    mode = "rb"
def repl(match):
    names = open("/dev/null", "r", match.end()).readlines()
    names.append("mode")
    open("/dev/null", getattr(Options, names[-1])).close()
    return ""
re.sub("r", repl, "r")

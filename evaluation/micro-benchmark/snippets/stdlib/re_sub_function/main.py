import re

def shout(match):
    return match.group().upper()

re.sub("a+", shout, "banana")

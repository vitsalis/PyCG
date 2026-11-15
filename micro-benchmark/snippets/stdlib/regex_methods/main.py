import re

pattern = re.compile("a+")
match = pattern.match("aa")
match.group()

import os.path
import re
def text():
    re.sub("a", "b", "c").upper()
def data():
    re.sub(b"a", b"b", b"c").lower()
def joined(base):
    os.path.join("a", base).title()
def unknown(pattern):
    re.sub(pattern, "b", "c").strip()
def unknown_first(base):
    os.path.join(base, "a").zfill(1)
def unknown_both(base, name):
    os.path.join(base, name).center(1)
text()
data()
joined(object())

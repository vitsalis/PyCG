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
text()
data()
joined(object())

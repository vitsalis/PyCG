
import ext
def f(): pass
def g(): pass

def use(count, text):
    ("ab" * count).upper()
    "abc"[1:].strip()
    "abc"[0].isdigit()
    b"abc"[1:].hex()
    for letter in "abc":
        letter.isalpha()
    comment = "/*"
    comment += text
    comment.endswith("*/")

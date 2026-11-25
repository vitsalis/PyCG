def shout(count):
    return ("ab" * count).upper()


def tail(text):
    return text[1:].strip()


comment = "/*"
comment += "x"
comment.endswith("*/")
shout(2)
tail("abc")
"abc"[0].isalpha()
f"{shout(1)}.{2}".rstrip("0")
for letter in "ab":
    letter.isdigit()

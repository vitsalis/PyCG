import sys


class Shout:
    def upper(self):
        return self


def label(value):
    text = "value = %s" % value
    if isinstance(text, str):
        return text
    if callable(text):
        return text()
    return Shout().upper()


label(sys.argv)

import re
import foo


class Box:
    def __iter__(self):
        return iter([])


def main(text, callback):
    for item in Box():
        re.compile(text).match(item)
    foo.get.bar()
    callback()

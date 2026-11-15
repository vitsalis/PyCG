def describe():
    return "parse error"


class ParseError(Exception):
    def __str__(self):
        return describe()


try:
    raise ParseError
except ParseError as error:
    text = str(error)
    line = f"{error}"

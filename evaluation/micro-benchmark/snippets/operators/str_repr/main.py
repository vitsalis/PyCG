class Point:
    def __str__(self):
        return "p"

    def __repr__(self):
        return "Point()"


class Plain:
    def __repr__(self):
        return "Plain()"


point = Point()
str(point)
repr(point)
text = f"{point!r}"
print(point)
str(Plain())

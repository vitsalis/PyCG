class Name(str):
    def __repr__(self):
        return "Name()"


class Failure(Exception):
    def __repr__(self):
        return "Failure()"


class Count(int):
    def __repr__(self):
        return "Count()"


def show(value):
    return f"{value}" + str(value) + "{}".format(value)


show(Name("a"))
show(Failure("b"))
show(Count(1))

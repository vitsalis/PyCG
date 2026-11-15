def check(value):
    pass


class Checked:
    def __set__(self, obj, value):
        check(value)


class Frozen:
    value = Checked()

    def __init__(self, value):
        object.__setattr__(self, "value", value)


Frozen(1)

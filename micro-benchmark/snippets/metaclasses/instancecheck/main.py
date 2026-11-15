def check(obj):
    return True


class Meta(type):
    def __instancecheck__(cls, obj):
        return check(obj)


class Duck(metaclass=Meta):
    pass


def check_number():
    return isinstance(1, Duck)


def check_duck():
    return isinstance(Duck(), Duck)


check_number()
check_duck()

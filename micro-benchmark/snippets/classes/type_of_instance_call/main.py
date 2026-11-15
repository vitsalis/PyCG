class Base:
    def __init__(self):
        pass


class Child(Base):
    def __init__(self):
        pass


def duplicate(obj):
    return type(obj)()


duplicate(Child())

class Base:
    def run(self):
        pass


class Middle(Base):
    def run(self):
        pass


class Child(Middle):
    pass


class Other:
    def run(self):
        pass


def pick(obj):
    try:
        super(Middle, obj).run()
    except TypeError:
        pass


pick(Child())
pick(Other())

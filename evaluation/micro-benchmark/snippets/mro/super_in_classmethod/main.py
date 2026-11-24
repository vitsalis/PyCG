class Base:
    @classmethod
    def create(cls):
        return cls()


class Child(Base):
    def __init__(self):
        pass

    @classmethod
    def create(cls):
        return super().create()


Child.create()

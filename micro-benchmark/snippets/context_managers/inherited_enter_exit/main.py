def audit():
    pass


class Base:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


class Audited(Base):
    def __exit__(self, *args):
        audit()


with Audited():
    pass

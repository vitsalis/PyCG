def default_handler():
    pass


def custom_handler():
    pass


class Base:
    handler = staticmethod(default_handler)


class Plain(Base):
    pass


class Custom(Base):
    handler = staticmethod(custom_handler)


Plain().handler()

class Meta(type):
    @staticmethod
    def tag():
        pass


class Factory(metaclass=Meta):
    @staticmethod
    def tag():
        pass


def by_owner_made(cls):
    cls.tag()


def by_instance_made(cls):
    cls.tag()


def by_class_made(cls):
    cls.tag()


def by_empty_star_made(cls):
    cls.tag()


def by_star_made(cls):
    cls.tag()


def by_false_made(cls):
    cls.tag()


def owner_wins_made(cls):
    cls.tag()


def outside_made(cls):
    cls.from_bytes(b"\x01", "big")


def helper():
    pass


static = staticmethod(helper)


def by_owner():
    classmethod(by_owner_made).__get__(None, Factory)()


def by_instance(factory):
    classmethod(by_instance_made).__get__(factory)()


def by_class():
    classmethod(by_class_made).__get__(Factory)()


def by_empty_star(factory):
    classmethod(by_empty_star_made).__get__(factory, *())()


def by_star(factory):
    classmethod(by_star_made).__get__(*[factory])()


def by_false():
    classmethod(by_false_made).__get__(False, Factory)()


def owner_wins(factory):
    classmethod(owner_wins_made).__get__(factory, Meta)()


def outside():
    classmethod(outside_made).__get__(None, int)()


def static_instance(factory):
    static.__get__(factory)()


def static_false():
    static.__get__(False, Factory)()


factory = Factory()
by_owner()
by_instance(factory)
by_class()
by_empty_star(factory)
by_star(factory)
by_false()
owner_wins(factory)
outside()
static_instance(factory)
static_false()

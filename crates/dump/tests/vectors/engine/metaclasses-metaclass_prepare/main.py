def make_namespace():
    return {}


class Meta(type):
    @classmethod
    def __prepare__(mcs, name, bases):
        return make_namespace()


class Model(metaclass=Meta):
    pass

def made():
    return 1


class plain(property):
    pass


class Meta(type):
    @property
    def kind(cls):
        return made()

    @plain
    def label(cls):
        return made()


class Model(metaclass=Meta):
    pass


def use_kind():
    return Model.kind


def use_label():
    return Model.label


use_kind()
use_label()

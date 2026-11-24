class constant(property):
    def __get__(self, instance, owner=None):
        return 0


class Model:
    @constant
    def value(self):
        return 1


def through_instance():
    return Model().value


def through_class():
    return Model.value


through_instance()
through_class()

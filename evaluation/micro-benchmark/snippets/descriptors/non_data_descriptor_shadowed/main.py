def compute():
    return 1


class Lazy:
    def __get__(self, obj, objtype=None):
        value = compute()
        obj.__dict__["value"] = value
        return value


class Model:
    value = Lazy()


def first_read(model):
    return model.value


def second_read(model):
    return model.value


model = Model()
first_read(model)
second_read(model)

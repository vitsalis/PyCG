class Meta(type):
    def create(cls):
        return cls()

    def describe(cls):
        pass


class Model(metaclass=Meta):
    def __init__(self):
        pass

    def describe(self):
        pass


Model.create()
Model().describe()

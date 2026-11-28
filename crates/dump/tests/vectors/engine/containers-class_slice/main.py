class Alias:
    def __class_getitem__(cls, item):
        return cls

    def run(self):
        pass


class Meta(type):
    def __getitem__(cls, item):
        return cls


class Indexed(metaclass=Meta):
    def run(self):
        pass


Alias[1:2]().run()
Indexed[1:2]().run()

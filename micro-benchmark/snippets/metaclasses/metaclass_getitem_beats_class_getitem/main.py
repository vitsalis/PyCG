class Meta(type):
    def __getitem__(cls, key):
        return key


class Palette(metaclass=Meta):
    def __class_getitem__(cls, key):
        return key


Palette["red"]

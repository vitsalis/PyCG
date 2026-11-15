class Meta(type):
    def __iter__(cls):
        return iter(cls.members)

    def __len__(cls):
        return len(cls.members)


class Colors(metaclass=Meta):
    members = ["red", "green"]


len(Colors)
for color in Colors:
    pass

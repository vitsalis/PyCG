from dataclasses import dataclass, field


def empty_tags():
    return []


def normalize(name):
    return name.lower()


@dataclass
class Item:
    name: str
    tags: list = field(default_factory=empty_tags)

    def __post_init__(self):
        self.name = normalize(self.name)


Item("A")

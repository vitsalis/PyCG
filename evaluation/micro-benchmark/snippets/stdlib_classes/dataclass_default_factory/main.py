from dataclasses import dataclass, field


def new_items():
    return []


def new_wishes():
    return []


@dataclass
class Cart:
    items: list = field(default_factory=new_items)


@dataclass
class Wishlist:
    items: list = field(default_factory=new_wishes)


Cart(items=[])
Wishlist()

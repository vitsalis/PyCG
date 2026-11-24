from typing import Annotated, get_type_hints


def positive(value):
    return value > 0


def non_empty(value):
    return value != ""


def set_price(price: Annotated[int, positive], label: Annotated[str, non_empty]):
    pass


hints = get_type_hints(set_price, include_extras=True)
for check in hints["price"].__metadata__:
    check(5)

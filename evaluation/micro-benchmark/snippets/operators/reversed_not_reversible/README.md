`reversed()` of an object without `__reversed__` needs both `__len__` and
`__getitem__`. `OnlyItems` and `OnlyLength` have one of them, so
`reversed()` raises `TypeError` without calling either: only `Row`'s methods
are called.

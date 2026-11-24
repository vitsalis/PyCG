class Pair:
    def __iter__(self):
        return iter((1, 2))


first, second = Pair()
values = [*Pair()]

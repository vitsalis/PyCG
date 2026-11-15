class Position:
    def __index__(self):
        return 1


class Amount:
    def __int__(self):
        return 5

    def __float__(self):
        return 5.0


items = ["a", "b"]
items[Position()]
range(Position())
int(Amount())
float(Amount())

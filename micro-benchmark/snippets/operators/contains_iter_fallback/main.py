class Basket:
    def __iter__(self):
        return iter(["apple"])


"apple" in Basket()

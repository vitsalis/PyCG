class Order:
    def __init__(self):
        self.items = [1, 2]

    def subtotal(self):
        return sum(self.items)

    def tax(self):
        return 1

    @property
    def total(self):
        return self.subtotal() + self.tax()


Order().total

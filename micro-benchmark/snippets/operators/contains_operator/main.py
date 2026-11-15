class Inventory:
    def __contains__(self, item):
        return True

    def __iter__(self):
        return iter([])


"apple" in Inventory()
"pear" not in Inventory()

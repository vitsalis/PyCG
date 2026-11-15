class Item:
    def __eq__(self, other):
        return True


items = [Item()]
Item() in items
items.index(Item())

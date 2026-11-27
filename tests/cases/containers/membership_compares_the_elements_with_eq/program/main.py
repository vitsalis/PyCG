
class Item:
    def __eq__(self, other):
        return True
class Items:
    def __iter__(self):
        yield Item()
class Searched:
    def __eq__(self, other):
        return False
def use():
    1 in Items()
    1 not in [Item()]
    Searched() in (1, 2)

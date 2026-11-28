
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
class Other:
    def __hash__(self): return 2
    def __eq__(self, other): return True
def same():
    key = Key()
    table = {key: 1}
    table[key]
def equal():
    table = {Key(): 1}
    table[Key()]
def stored():
    table = {}
    table[Other()] = 1
same()
equal()
stored()

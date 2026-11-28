
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return False
def compare(a, b):
    return {a} > {b}
compare(Key(), Key())

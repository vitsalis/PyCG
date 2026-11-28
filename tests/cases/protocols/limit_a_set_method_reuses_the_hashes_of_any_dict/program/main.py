
class Key:
    def __hash__(self): return 0
source = {Key(): 1}
def use():
    set().intersection(source)
use()

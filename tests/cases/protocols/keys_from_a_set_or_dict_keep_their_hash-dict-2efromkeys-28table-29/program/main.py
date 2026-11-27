
class Key:
    def __hash__(self): return 1
    def __eq__(self, other): return True
keys = {Key()}
table = {Key(): 1}
def use(keys, table):
    dict.fromkeys(table)
use(keys, table)

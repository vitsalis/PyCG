
import copy
import dataclasses
@dataclasses.dataclass
class Data:
    x: int
    def show(self): pass
def use():
    copy.replace(Data(1), x=2).show()
use()


import lib
class Items(list[int]):
    def __getitem__(self, index): pass
class Members(list):
    def __iter__(self):
        return iter([])
class Error(Exception):
    def __getitem__(self, index): pass
class Unknown(lib.Base):
    def __getitem__(self, index): pass
class Number(int):
    def __str__(self):
        return ""
def use(items, members, error, unknown, number):
    for x in items: pass
    1 in members
    for x in error: pass
    for x in unknown: pass
    format(number)
use(Items(), Members(), Error(), Unknown(), Number())

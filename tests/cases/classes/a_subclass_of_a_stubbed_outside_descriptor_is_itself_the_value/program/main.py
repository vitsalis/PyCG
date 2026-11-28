
import functools
class lazy(functools.cached_property):
    def describe(self): pass
class Report:
    @lazy
    def data(self): pass
def use():
    Report().data.describe()
use()

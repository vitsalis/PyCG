
import ext
class lazy(ext.Descriptor):
    def describe(self): pass
class Report:
    @lazy
    def data(self): pass
def use():
    Report().data.describe()
use()

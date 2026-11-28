def f(): pass
def g(): pass
def h(): pass
import collections
from collections import OrderedDict
OrderedDict(a=f).pop('a')()

import itertools
def use(it):
    first = next(it)
    second = next(it)
    return first, second
use(itertools.groupby([1, 2]))

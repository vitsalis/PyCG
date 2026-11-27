
import itertools
def use(it):
    first = next(it)
    second = next(it)
    return first, second
use(itertools.zip_longest([1, 2]))

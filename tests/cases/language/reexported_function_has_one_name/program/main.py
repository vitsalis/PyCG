
import pkg.impl
from pkg import func
from pkg.impl import func as same
func()
same()
pkg.func()
def through_submodule():
    pkg.impl.func()

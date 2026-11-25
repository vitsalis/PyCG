from os.path import *
from string import *


def build():
    return join("a", basename("b/c"))


build()
Template("$x").substitute(x=1)
capwords("a b")


def f(): pass
def g(): pass
def h(): pass

import ext
import typing
from typing import TYPE_CHECKING, cast
flag = False
def use(value):
    if TYPE_CHECKING:
        value = cast(int, value)
    if typing.TYPE_CHECKING:
        f()
    if flag:
        g()
def rebinding():
    global flag
    flag = ext.value

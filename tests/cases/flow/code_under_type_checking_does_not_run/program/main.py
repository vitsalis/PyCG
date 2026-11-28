
def f(): pass
def g(): pass
def h(): pass

from typing import TYPE_CHECKING
import typing
import typing_extensions as extensions
if TYPE_CHECKING:
    from plugins import Plugin
    f()
else:
    g()
if typing.TYPE_CHECKING or extensions.TYPE_CHECKING:
    f()
if not TYPE_CHECKING:
    h()
def use():
    Plugin()

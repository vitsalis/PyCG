
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from xml.etree.ElementTree import Element
def use(x: "Element"):
    x.find("child")

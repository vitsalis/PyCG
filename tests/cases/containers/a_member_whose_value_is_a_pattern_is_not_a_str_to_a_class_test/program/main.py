
from enum import Enum
def suffix():
    return "x"
class E(Enum):
    A = "enum_" + suffix()
item = E.A
if not isinstance(item, str):
    kept = item


import json
import sys
def dump(value):
    return sys.modules["json"].dumps(value)

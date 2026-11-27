
from collections.abc import Mapping
class Partial(Mapping):
    def __init__(self): pass
    def __getitem__(self, key): pass
class Full(Partial):
    def __init__(self): pass
    def __iter__(self): pass
    def __len__(self): pass
Partial()
Full()

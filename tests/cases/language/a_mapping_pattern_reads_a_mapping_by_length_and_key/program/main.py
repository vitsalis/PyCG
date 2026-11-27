
import ext
def f(): pass
def g(): pass
def h(): pass

from collections.abc import Mapping
class Config(Mapping):
    def __getitem__(self, key):
        return f
    def __iter__(self):
        return iter(["run"])
    def __len__(self):
        return 1
def use(value):
    match value:
        case {"run": handler}:
            handler()
use(Config())

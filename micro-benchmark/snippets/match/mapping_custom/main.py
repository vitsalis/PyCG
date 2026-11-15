from collections.abc import Mapping

def func1():
    pass

class Config(Mapping):
    def __getitem__(self, key):
        return func1

    def __iter__(self):
        return iter(["run"])

    def __len__(self):
        return 1

match Config():
    case {"run": handler}:
        handler()

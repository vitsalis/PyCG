
class Node:
    __slots__ = {"value": "the value", "__weakref__": None}
    def __getattr__(self, name): pass
    def run(self):
        self.value
        self.__weakref__

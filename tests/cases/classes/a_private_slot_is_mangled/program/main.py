
class Node:
    __slots__ = ("__parent",)
    def __getattr__(self, name): pass
    def run(self):
        self.__parent

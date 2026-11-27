
def fetch(): pass
class Lazy:
    def __get__(self, obj, owner=None):
        raise AttributeError("value")
class Node:
    value = Lazy()
    @property
    def parent(self):
        raise AttributeError("parent")
    def __getattr__(self, name):
        return fetch
def use():
    node = Node()
    node.parent()
    node.value()

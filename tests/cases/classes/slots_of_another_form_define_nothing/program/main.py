
NAMES = ("value",)
class Node:
    __slots__ = NAMES
    def __getattr__(self, name): pass
    def run(self):
        self.value

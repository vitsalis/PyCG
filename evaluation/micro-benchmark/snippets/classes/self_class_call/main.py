class Node:
    def __init__(self):
        pass

    def clone(self):
        return self.__class__()


class Leaf(Node):
    def __init__(self):
        pass


Leaf().clone()

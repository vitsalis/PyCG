class Node:
    def __str__(self):
        return "str"

    def __repr__(self):
        return "repr"


def describe(node):
    message = "%r is its own parent"
    return message % (node,)


describe(Node())


import ext
class Node:
    def __init__(self, parent=None):
        self.parent = parent
    def walk(self):
        return self.parent
def f(): pass
def g(): pass
def run(node, handler=f):
    while node:
        handler()
        try:
            node = node.walk()
            if ext.flag:
                handler = node
                continue
            handler = g
        except ValueError as error:
            handler = error
            break
        finally:
            done = handler
    else:
        done = None
    with ext.lock:
        node = Node(node)
    return node, done
class C:
    method = f
    for item in (f, g):
        method = item
    method = staticmethod(method)
result = run(Node(Node()))
result[0].walk()
C.method()


import ext
class Node:
    def walk(self):
        self.walk()
        return self.next.walk()
node = Node()
node.next = node
node.walk()
cursor = ext.start
while cursor:
    cursor.visit()
    cursor = cursor.parent
def recurse(n):
    return recurse(recurse)
recurse(recurse)
class Callable:
    pass
Callable.__call__ = Callable()
Callable()()
class Init:
    pass
Init.__init__ = Init
Init()

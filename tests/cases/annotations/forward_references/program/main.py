
class Node:
    def connect(self, other: "Node"):
        other.run()
    def run(self): pass
def use(x: "Later", y: "AliasT"):
    x.go()
    y.go()
class Later:
    def go(self): pass
AliasT = Later | None

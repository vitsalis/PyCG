
import ext
def f(): pass
def g(): pass
def h(): pass

class Falsy:
    def __bool__(self): return False
class Compared:
    def __eq__(self, other): return Falsy()
class Holder:
    compared = Compared()
def literal(subject):
    match subject:
        case 0.5: pass
def singletons(subject):
    match subject:
        case None: pass
        case True: pass
def reflected():
    match 0.5:
        case Holder.compared: pass
literal(Compared())
singletons(Compared())

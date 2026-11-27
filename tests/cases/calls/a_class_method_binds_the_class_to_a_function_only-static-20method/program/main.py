def wrapped(owner):
    owner.target()
class C:
    @staticmethod
    def target(): pass
    make = classmethod(staticmethod(wrapped))
C.make()

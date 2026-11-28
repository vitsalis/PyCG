class Maker:
    def __init__(self, owner):
        owner.target()
class C:
    @staticmethod
    def target(): pass
    make = classmethod(Maker)
C.make()

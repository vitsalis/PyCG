class Helper:
    def __call__(self, owner):
        owner.target()
class C:
    @staticmethod
    def target(): pass
    make = classmethod(Helper())
C.make()

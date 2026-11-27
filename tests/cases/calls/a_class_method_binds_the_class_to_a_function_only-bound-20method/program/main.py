class Helper:
    def run(self, owner):
        owner.target()
class C:
    @staticmethod
    def target(): pass
    make = classmethod(Helper().run)
C.make()

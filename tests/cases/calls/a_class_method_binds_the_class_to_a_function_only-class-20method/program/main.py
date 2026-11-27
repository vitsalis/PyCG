class A:
    @classmethod
    def run(a, owner):
        owner.target()
class C:
    @staticmethod
    def target(): pass
    make = classmethod(A.run)
C.make()

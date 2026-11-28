
class A:
    @staticmethod
    def s(obj):
        obj.run()
class B:
    s = A.s
    def run(self): pass
B().s()

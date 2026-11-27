
class C:
    class Inner:
        def m(self): pass
class Other:
    def m(self): pass
class Meta(type):
    def __getattr__(cls, name): return Other
class Dynamic(metaclass=Meta): pass
c = C()
def member(x: "C.Inner"): x.m()
def of_instance(x: "c.Inner"): x.m()
def of_function(x: "member.Inner"): x.m()
def through_getattr(x: "Dynamic.Inner"): x.m()

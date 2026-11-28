
def helper(self): pass
class C:
    __hook = helper
    def __f(self): pass
    def g(self):
        self.__f()
        def inner():
            self.__hook()
        inner()
class D(C):
    def __f(self): pass
    def h(self):
        self.__f()
class _Private:
    def __p(self): pass
C()._C__f()
D().g()
D().h()
_Private()._Private__p()

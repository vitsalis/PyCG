class A:
    def method(self):
        pass


def outer():
    pass


A.added = outer
namespace = vars(A)
namespace["method"](A())
namespace["added"]()

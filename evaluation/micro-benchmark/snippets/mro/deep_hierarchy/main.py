class A:
    def ping(self):
        self.pong()

    def pong(self):
        pass


class B(A):
    pass


class C(B):
    def pong(self):
        pass


class D(C):
    pass


class E(D):
    pass


E().ping()

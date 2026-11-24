def greet(self):
    pass


class Base:
    def __init__(self):
        pass


Dynamic = type("Dynamic", (Base,), {"greet": greet})
Dynamic().greet()

def work(): pass
def fetched(): pass
class Base:
    def __init__(self):
        self.handler = work
class Lazy(Base):
    def __init__(self):
        super().__init__()
        if work:
            self.__own = work
    def __getattr__(self, name):
        return fetched
    def run(self):
        self.__own()
        self.handler()
    def other(self):
        self.missing()
lazy = Lazy()
lazy.run()
lazy.other()

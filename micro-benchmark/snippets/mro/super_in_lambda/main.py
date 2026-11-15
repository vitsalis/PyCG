class Base:
    def load(self):
        pass


class Child(Base):
    def load(self):
        call_parent = lambda obj: super().load()
        call_parent(self)


Child().load()

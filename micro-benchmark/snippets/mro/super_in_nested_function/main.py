class Base:
    def load(self):
        pass


class Child(Base):
    def load(self):
        def helper(obj):
            super().load()

        helper(self)


Child().load()

class Base:
    def greet(self):
        pass


class Child(Base):
    def greet(self):
        pass


child = Child()
Base.greet(child)

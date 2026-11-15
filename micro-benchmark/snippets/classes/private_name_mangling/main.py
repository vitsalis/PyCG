class Base:
    def run(self):
        self.__step()

    def __step(self):
        pass


class Child(Base):
    def __step(self):
        pass


Child().run()

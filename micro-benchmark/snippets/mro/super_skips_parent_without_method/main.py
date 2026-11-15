class Base:
    def close(self):
        pass


class Middle(Base):
    pass


class Leaf(Middle):
    def close(self):
        super().close()


Leaf().close()

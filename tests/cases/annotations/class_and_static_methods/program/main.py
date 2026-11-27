
class Base:
    @classmethod
    def make(cls):
        cls.build()
    @classmethod
    def build(cls): pass
    @staticmethod
    def util(target=None):
        target.run()
    def run(self): pass
class Child(Base):
    @classmethod
    def build(cls): pass

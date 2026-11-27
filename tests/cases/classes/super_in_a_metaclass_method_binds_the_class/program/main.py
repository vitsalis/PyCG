
class Base(type):
    def describe(cls):
        cls.hook()
class Meta(Base):
    def describe(cls):
        super().describe()
class Model(metaclass=Meta):
    @staticmethod
    def hook(): pass
class Other(metaclass=Base):
    @staticmethod
    def hook(): pass
Meta.describe(Model)

from enum import Enum


class Color(Enum):
    RED = 1
    GREEN = 2

    def describe(self):
        return self.name.lower()

    @classmethod
    def default(cls):
        return cls.RED


Color.RED.describe()
Color.default()

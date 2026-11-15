from abc import ABC, abstractmethod


class Shape(ABC):
    @abstractmethod
    def area(self):
        raise NotImplementedError

    def describe(self):
        return self.area()


class Square(Shape):
    def area(self):
        return 4


Square().describe()

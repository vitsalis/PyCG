class Animal:
    def describe(self):
        pass


class Dog(Animal):
    def describe(self):
        super().describe()


Dog().describe()

class Animal:
    def speak(self):
        pass


class Dog(Animal):
    def speak(self):
        pass


def talk(animal: Animal) -> None:
    animal.speak()


talk(Dog())

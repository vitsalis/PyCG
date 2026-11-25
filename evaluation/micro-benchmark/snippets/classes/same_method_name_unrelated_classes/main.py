class Dog:
    def speak(self):
        pass


class Robot:
    def speak(self):
        pass


def talk(speaker):
    speaker.speak()


dog = Dog()
robot = Robot()
talk(dog)

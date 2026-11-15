class Cat:
    def speak(self):
        pass


class Robot:
    def speak(self):
        pass


def talk(speaker: Cat) -> None:
    speaker.speak()


talk(Robot())

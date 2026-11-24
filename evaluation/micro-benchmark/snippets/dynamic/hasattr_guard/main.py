class Duck:
    def quack(self):
        pass

class Robot:
    def beep(self):
        pass

def speak(thing):
    if hasattr(thing, "quack"):
        thing.quack()

speak(Duck())
speak(Robot())

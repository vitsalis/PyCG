class Base:
    def __new__(cls, *args):
        instance = super().__new__(cls)
        instance.ready = True
        return instance


class Loud(Base):
    def speak(self):
        pass

    def __getattr__(self, name):
        return self.speak


class Quiet(Base):
    def speak(self):
        pass


Loud()
Quiet().speak()

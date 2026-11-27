
import ext
def f(): pass
def g(): pass

class Root:
    def __new__(cls, *args):
        instance = super(Root, cls).__new__(cls)
        instance.flag = False
        return instance
class Base(Root):
    def __new__(cls, *args, **kwargs):
        instance = super().__new__(cls, *args, **kwargs)
        instance.done = Done()
        return instance
    def finish(self):
        self.done.run()
class Done:
    def run(self):
        pass
class Loud(Base):
    def __getattr__(self, name):
        return f
class Quiet(Base):
    def speak(self):
        pass
Loud()
quiet = Quiet()
quiet.speak()
quiet.finish()

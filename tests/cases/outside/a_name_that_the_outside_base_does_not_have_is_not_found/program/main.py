
import abc
class Mixin:
    def helper(self): pass
class Task(abc.ABC, Mixin):
    def run(self):
        self.sleep()
        self.helper()


def decorate(function):
    def wrapper(*args):
        args[0].before()
        return function(*args)
    return wrapper
class C:
    def before(self): pass
    @decorate
    def run(self):
        self.before()

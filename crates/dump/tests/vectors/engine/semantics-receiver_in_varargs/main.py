class Box:
    def method(*args):
        args[0].other()

    def other(self):
        pass


Box().method()

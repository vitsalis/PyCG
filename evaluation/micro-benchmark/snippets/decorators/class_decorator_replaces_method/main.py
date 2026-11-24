def log_start(cls):
    original = cls.start

    def start(self):
        return original(self)

    cls.start = start
    return cls


@log_start
class Engine:
    def start(self):
        pass


Engine().start()

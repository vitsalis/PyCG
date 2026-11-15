def traced(method):
    def wrapper(self):
        return method(self)

    return wrapper


class Service:
    @traced
    def start(self):
        pass


Service().start()

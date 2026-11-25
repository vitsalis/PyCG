class Service:
    def start(self):
        pass

    def stop(self):
        pass


def run(service, action: str = "start"):
    getattr(service, action)()


run(Service())

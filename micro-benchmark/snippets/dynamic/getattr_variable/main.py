class Service:
    def start(self):
        pass

    def stop(self):
        pass

name = "stop"
service = Service()
getattr(service, name)()

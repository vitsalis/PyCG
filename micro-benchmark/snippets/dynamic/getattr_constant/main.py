class Service:
    def start(self):
        pass

    def stop(self):
        pass

service = Service()
getattr(service, "start")()

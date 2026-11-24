import ext

class Service:
    def __init__(self):
        self.client = ext.Client()

    def run(self):
        self.client.send()

Service().run()

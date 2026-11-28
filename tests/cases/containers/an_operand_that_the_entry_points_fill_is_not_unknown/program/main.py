
class App:
    def run(self):
        pass
class Request:
    def __init__(self, environ):
        self.environ = environ
    def __getattr__(self, name):
        return self.environ["ext.%s" % name]
    def use(self):
        self.config.run()
Request({"app": App()})

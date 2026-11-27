
class App:
    def run(self):
        pass
class Request:
    def __init__(self, environ):
        self.environ = environ
        environ["app"] = App()
    def __getattr__(self, name):
        return self.environ["ext.%s" % name]
request = Request({})
request.config.run()

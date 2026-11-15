class Router:
    def route(func):
        func.routed = True
        return func

    @route
    def index(self):
        pass


Router().index()

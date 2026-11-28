
def route(path):
    def register(f):
        return f
    return register
@route("/")
def index(): pass
index()

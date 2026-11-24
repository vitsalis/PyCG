def render_page():
    pass


def log_request():
    pass


hooks = {"render.page": render_page, "log": log_request}


def run(name):
    hooks["render.%s" % name]()


run("page")

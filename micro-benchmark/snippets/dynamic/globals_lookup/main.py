def handle_get():
    pass

def handle_post():
    pass

kind = "post"
globals()["handle_" + kind]()

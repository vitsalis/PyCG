
class Failure(Exception):
    def __init__(self, message="failed"):
        self.message = message
class Plain(Exception):
    pass
class Cause(Exception):
    def __init__(self): pass
def check(flag):
    if flag:
        raise Failure
    raise Plain from Failure()
def chain():
    raise Plain from Cause

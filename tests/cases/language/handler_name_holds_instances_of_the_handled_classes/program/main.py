
class Error(Exception):
    def report(self): pass
class Timeout(Error):
    def report(self): pass
class Other(Exception):
    def report(self): pass
def run():
    raise Timeout()
def other():
    raise Other()
try:
    run()
except Error as error:
    error.report()

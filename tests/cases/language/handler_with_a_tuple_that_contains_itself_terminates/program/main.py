
class Error(Exception):
    def report(self): pass
kinds = ()
kinds = (kinds, Error)
def run():
    raise Error()
try:
    run()
except kinds as error:
    error.report()

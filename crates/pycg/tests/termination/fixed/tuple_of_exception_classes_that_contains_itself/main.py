class Error(Exception): pass
kinds = ()
kinds = (kinds, Error)
try:
    raise Error()
except kinds as error:
    pass

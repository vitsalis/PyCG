
try:
    pass
except ValueError as error:
    error.with_traceback(None)
    error.no_such_method()

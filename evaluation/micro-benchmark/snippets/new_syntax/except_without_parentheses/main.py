def connect():
    raise TimeoutError

def retry():
    pass

try:
    connect()
except ConnectionError, TimeoutError:
    retry()

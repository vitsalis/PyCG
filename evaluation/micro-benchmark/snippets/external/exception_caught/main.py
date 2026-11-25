import ext

def recover():
    pass

try:
    ext.connect()
except ext.Timeout:
    recover()

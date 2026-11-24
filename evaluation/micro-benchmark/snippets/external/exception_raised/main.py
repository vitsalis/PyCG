import ext

def recover():
    pass

try:
    raise ext.Error("failed")
except ext.Error:
    recover()

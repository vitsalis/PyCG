import os

def log(msg):
    print (msg)

def to_mod_name(name):
    return os.path.splitext(name)[0].replace("/", ".")

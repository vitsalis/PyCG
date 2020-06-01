import os

def get_lambda_name(counter):
    return "<lambda{}>".format(counter)

def get_dict_name(counter):
    return "<dict{}>".format(counter)

def join_ns(*args):
    return ".".join([arg for arg in args])

def to_mod_name(name, package=None):
    return os.path.splitext(name)[0].replace("/", ".")

import os

def get_lambda_name(counter):
    return "<lambda{}>".format(counter)

def join_ns(ns1, ns2):
    return "{}.{}".format(ns1, ns2)

def to_mod_name(name):
    return os.path.splitext(name)[0].replace("/", ".")

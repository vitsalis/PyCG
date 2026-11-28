import tokenize
import urllib.request
from importlib.resources import files


def fetch(url):
    response = urllib.request.urlopen(url)
    return response.geturl()


def source(path):
    with tokenize.open(path) as f:
        return f.read()


def font(name):
    return files("fonts").joinpath(name)


fetch("http://example.org")
source("main.py")
font("standard.flf")

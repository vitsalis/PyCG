import requests
import untyped
def fetch(url):
    untyped.get(url).json()
    return requests.get(url).json()


from ._vendor import requests
def fetch():
    return requests.get("u").json()

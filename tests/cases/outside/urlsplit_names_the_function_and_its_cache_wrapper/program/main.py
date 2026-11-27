
import urllib.parse
from urllib.parse import urlsplit
def host(url):
    urllib.parse.urlsplit(url)
    return urlsplit(url).netloc


import requests
import yaml
from google.protobuf import json_format
class Client(requests.Session):
    def fetch(self, url):
        return self.get(url).json(object_hook=self.hook)
    def hook(self, pairs): pass
with Client() as client:
    client.fetch("u")
    client.get("u").headers.get("k")
yaml.add_constructor("!x", Client.hook)
yaml.SafeLoader("a").get_single_data()
json_format.MessageToJson(None).upper()

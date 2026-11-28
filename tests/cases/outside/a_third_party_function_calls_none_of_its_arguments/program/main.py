
import requests
import yaml
def construct(loader, node):
    pass
def hook(pairs):
    pass
yaml.add_constructor("!x", construct)
requests.get("u").json(object_hook=hook)
list(map(hook, [1]))


import yaml
from yaml.loader import SafeLoader
yaml.load("a: 1", Loader=yaml.SafeLoader)
yaml.SafeLoader("a: 1").get_single_data()
SafeLoader("a: 1").get_single_data()
try:
    yaml.safe_load("a: 1")
except yaml.YAMLError as error:
    error.with_traceback(None)


import re
import logging
import collections
pattern = re.compile("a+")
pattern.match("aa").group()
logging.getLogger("app").info("started")
cache = collections.OrderedDict()
cache.move_to_end("k")
cache.get("k")

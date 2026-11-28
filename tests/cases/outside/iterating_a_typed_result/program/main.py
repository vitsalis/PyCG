
import re
for match in re.finditer("a", "aa"):
    match.span()

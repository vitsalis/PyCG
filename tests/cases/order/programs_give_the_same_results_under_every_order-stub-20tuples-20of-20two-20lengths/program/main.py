
import os.path
for split in (os.path.split, os.path.splitroot):
    head = split("/tmp/file")[0]
    head.upper()

import os.path
for split in (os.path.split, os.path.splitroot):
    split('/tmp/file')

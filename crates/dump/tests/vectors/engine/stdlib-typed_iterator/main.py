import csv
import io

for row in csv.DictReader(io.StringIO("a\n1")):
    pass

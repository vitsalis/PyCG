
class Table(dict):
    pass
def walk(table):
    for key in table:
        key.strip()
    return table.copy()
first = walk(Table(a=1))
walk(Table(b=2)); walk(Table(c=3))

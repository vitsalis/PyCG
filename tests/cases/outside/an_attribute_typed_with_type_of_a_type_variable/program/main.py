
from dataclasses import dataclass, fields
@dataclass
class Record:
    value: int
def use():
    fields(Record)[0].type

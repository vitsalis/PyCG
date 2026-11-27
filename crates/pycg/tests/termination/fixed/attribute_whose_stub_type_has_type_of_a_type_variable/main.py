from dataclasses import dataclass, fields
@dataclass
class R:
    value: int
fields(R)[0].type


from typing import TYPE_CHECKING
class Table:
    def insert(self):
        self.storage()
    def storage(self): pass
def with_typehint(baseclass):
    if TYPE_CHECKING:
        return baseclass
    return object
TableBase = with_typehint(Table)
class Database(TableBase):
    def __getattr__(self, name):
        return getattr(Table(), name)
def later():
    TableBase().insert()

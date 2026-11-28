
from ext import Base
import other.pkg as alias
class A(Base):
    def run(self):
        self.setup()
A().run()
alias.tool.make().build()

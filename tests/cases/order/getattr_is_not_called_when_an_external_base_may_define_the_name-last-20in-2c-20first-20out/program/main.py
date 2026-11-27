
import ext
class C(ext.Base):
    def __getattr__(self, name):
        pass
C().f

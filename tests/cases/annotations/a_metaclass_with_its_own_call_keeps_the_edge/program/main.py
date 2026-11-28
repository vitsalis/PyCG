
import abc, enum
def lookup(kind: enum.EnumMeta, meta: abc.ABCMeta):
    kind(1)
    meta()

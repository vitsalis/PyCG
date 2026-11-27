
__all__ = ["a"] + ["b"]
__all__ += ("c",)
def a(): pass
def b(): pass
def c(): pass
def d(): pass

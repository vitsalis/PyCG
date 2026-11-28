
try:
    from shapes import Square
except ImportError:
    from shapes import Shape
    def report(shape: Shape) -> None: ...

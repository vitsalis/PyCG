Since Python 3.14 (PEP 649), annotations are evaluated only when they are read.
Nothing reads them, so the edge `main -> main.make_type` must not appear.
Python 3.12 and 3.13 evaluate annotations when the function is defined.

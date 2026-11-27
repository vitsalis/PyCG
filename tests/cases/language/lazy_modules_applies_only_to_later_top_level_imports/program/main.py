
import report
__lazy_modules__ = ["audit", "report"]
try:
    import audit
except ImportError:
    pass

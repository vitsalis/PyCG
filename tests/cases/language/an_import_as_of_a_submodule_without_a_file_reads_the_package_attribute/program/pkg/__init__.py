
import sys
from . import real
alias = real
sys.modules[__name__ + ".alias"] = real

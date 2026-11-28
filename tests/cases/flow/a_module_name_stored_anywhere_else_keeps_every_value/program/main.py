import config
import pkg.flag
from config import IMPORTED

GLOBAL = False
AUGMENTED = 0
AUGMENTED += 1
DELETED = False
del DELETED
DELETED = False
CONDITIONAL = False
if config.ready:
    CONDITIONAL = True

def by_global(): pass
def by_augmented(): pass
def by_deletion(): pass
def by_condition(): pass

def enable():
    global GLOBAL
    GLOBAL = True

def run():
    if GLOBAL:
        by_global()
    if AUGMENTED:
        by_augmented()
    if DELETED:
        by_deletion()
    if CONDITIONAL:
        by_condition()

IMPORTED = True

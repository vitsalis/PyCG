import sys

ready = sys.argv
STORED = False
SET = False
DELETED_ATTRIBUTE = False
IMPORTED = False
KEYWORD = False

def by_attribute(): pass
def by_setattr(): pass
def by_attribute_deletion(): pass
def by_importer(): pass
def by_keyword(): pass

def run():
    if STORED:
        by_attribute()
    if SET:
        by_setattr()
    if DELETED_ATTRIBUTE:
        by_attribute_deletion()
    if IMPORTED:
        by_importer()
    if KEYWORD:
        by_keyword()

def configure(module):
    module.STORED = True
    setattr(module, "SET", True)
    del module.DELETED_ATTRIBUTE
    vars(module).update(KEYWORD=True)

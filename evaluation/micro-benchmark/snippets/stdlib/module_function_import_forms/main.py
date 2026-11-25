import os
import os.path as osp
from os import path

join = os.path.join

def via_module():
    os.path.join("a", "b")

def via_from():
    path.join("a", "b")

def via_as():
    osp.join("a", "b")

def via_alias():
    join("a", "b")

via_module()
via_from()
via_as()
via_alias()

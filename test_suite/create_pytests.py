#!/usr/bin/env python3

import os

SNIPPETS_DIR = "./snippets"

base_template = """
import os

from base import TestBase

class {cls}Test(TestBase):
    snippet_dir = "{dir}"
"""

test_template = """
    def test_{name}(self):
        self.validate_snippet(self.get_snippet_path("{name}"))
"""

def create_test_case(name):
    test_name = name + "_test.py"
    # TODO: capitalize
    capitalized = "".join([x.title() for x in name.split("_")])
    template = base_template.format(
        cls=capitalized,
        dir=name
    )
    for name in os.listdir(os.path.join(SNIPPETS_DIR, name)):
        if name == "." or name == "..":
            continue
        template += test_template.format(name=name)

    with open(test_name, "w+") as f:
        f.write(template)

for name in os.listdir(SNIPPETS_DIR):
    if name == "." or name == "..":
        continue

    create_test_case(name)

# Copyright (c) 2021 Ani Hovhannisyan.
#
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.

# This file checks content of the source directory and cleans it up.
# If there're broken files then those are moved to the destination directory.
# The "broken" definition is used for empty, or syntax errored files.
# Usage: python [script_file.py] -dir [source directory path] -out [future path]

import argparse
import os
import re
import ast

def parse_cmd_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-dir",
        help="Directory path containing independent code to be cleaned up",
        default=None
    )
    parser.add_argument(
        "-out",
        help="Output path where should be moved broken or empty files",
        default=None
    )

    args = parser.parse_args()
    return args

def get_cleared_python_code(filename):
    file_content = ""
    with open(filename, "rt") as f:
        for line in f:
            if re.search(r'(^\s+\%)|(^\%)', line):
                line = "#" + line
            if re.search(r'(^\s+\!)|(^\!)', line):
                line = "#" + line
            file_content = file_content + line
    return file_content

def has_syntax_error(filename):
    file_content = get_cleared_python_code(filename)
    try:
        ast_parse = ast.parse(file_content)
        return False
    except Exception as e:
        return True

def is_empty_files(filepath):
    if 0 == os.stat(filepath).st_size:
        return True
    else:
        return False

def move_broken_files_to_dest(broken_files_list, dest):
    if not os.path.isdir(dest):
        os.makedirs(dest)
        print("Created new output directory:", dest)

    for f in broken_files_list:
        new_path = os.sep.join([dest, os.path.basename(f)])
        print("Broken file:", f, "moved to", new_path, "path.")
        os.rename(f, new_path)

def analyse_directory_content(path, dest):
    fileslist = []
    broken_files_list = []
    for (dirpath, dirnames, filenames) in os.walk(path):
        for filename in filenames:
            filepath = os.sep.join([dirpath, filename])
            fileslist.append(filepath)
            if is_empty_files(filepath):
                broken_files_list.append(filepath)
            elif has_syntax_error(filepath):
                broken_files_list.append(filepath)
    move_broken_files_to_dest(broken_files_list, dest)

def main():
    args = parse_cmd_args()
    analyse_directory_content(args.dir, args.out)

if __name__ == "__main__":
    main()

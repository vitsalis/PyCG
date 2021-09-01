#
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
#

# Line Number class formats the JSON output.
# By passing --lineno argument only node and its line number is outputed.

import re

from .base import BaseFormatter

from pycg import utils

class LineNumber(BaseFormatter):
    def __init__(self, cg_generator):
        self.lines_graph = cg_generator.output_lg()

    def generate(self):
        output_lg = {}
        for node in self.lines_graph:
            linenums = self.lines_graph[node]
            for i in range(len(linenums)):
                if linenums[i] in output_lg:
                    output_lg[linenums[i]].append(node)
                else:
                    output_lg[linenums[i]] = [node]
        return output_lg

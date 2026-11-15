#
# Copyright (c) 2026 Vitalis Salis.
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
"""The document that PyCG writes (docs/format.md), and how to read it."""

import json

# The name and version of the format, which a reader checks.
FORMAT = "pycg/1"


def dumps(document):
    """The text of `document`: compact, with sorted keys, so the same
    document is the same bytes."""
    return json.dumps(document, sort_keys=True, separators=(",", ":"))


def edges(document):
    """The classic call graph of `document`: each node mapped to the sorted
    names it calls. The nodes are the modules and functions of
    `definitions` and the names of `outside`; the edges go from each caller
    to each callee of each of its sites. A document of another format is
    refused."""
    if document.get("format") != FORMAT:
        raise ValueError(f"not a {FORMAT} document: {document.get('format')!r}")
    graph = {
        name: set()
        for name, definition in document["definitions"].items()
        if definition["kind"] != "class"
    }
    graph.update((name, set()) for name in document["outside"])
    for caller, sites in document["calls"].items():
        for site in sites:
            graph[caller].update(site["callees"])
    return {name: sorted(graph[name]) for name in sorted(graph)}

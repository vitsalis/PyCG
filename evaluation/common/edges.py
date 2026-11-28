FORMAT = "pycg/1"


def edges(document):
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

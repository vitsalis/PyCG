import os

from pkg_resources import Requirement

from .base import BaseFormatter

from pycg import utils

class Fasten(BaseFormatter):
    def __init__(self, cg_generator, package, product, forge, version, timestamp):
        self.cg_generator = cg_generator
        self.internal_mods = self.cg_generator.output_internal_mods() or {}
        self.external_mods = self.cg_generator.output_external_mods() or {}
        self.classes = self.cg_generator.output_classes() or {}
        self.edges = self.cg_generator.output_edges() or []
        self.unique = 0
        self.namespace_map = {}
        self.package = package
        self.product = product
        self.forge = forge
        self.version = version
        self.timestamp = timestamp

    def get_unique_and_increment(self):
        unique = self.unique
        self.unique += 1
        return unique

    def to_uri(self, modname, name="", external=False):
        prefix = ""
        if external:
            prefix = "/"

        cleared = name
        if name:
            if not name.startswith(modname):
                raise Exception("name should start with modname", name, modname)

            cleared = name[len(modname):]
            if cleared.startswith("."):
                cleared = cleared[1:]

        return f"{prefix}/{modname}/{cleared}"

    def find_dependencies(self, package_path):
        res = []
        requirements_path = os.path.join(package_path, "requirements.txt")

        if not os.path.exists(requirements_path):
            return res

        reqs = []
        with open(requirements_path, "r") as f:
            lines = [l.strip() for l in f.readlines()]

        for line in lines:
            req = Requirement.parse(line)

            product = req.unsafe_name
            specs = req.specs

            constraints = []

            def add_range(begin, end):
                if begin and end:
                    if begin[1] and end[1]:
                        constraints.append(f"[{begin[0]}..{end[0]}]")
                    elif begin[1]:
                        constraints.append(f"[{begin[0]}..{end[0]})")
                    elif end[1]:
                        constraints.append(f"({begin[0]}..{end[0]}]")
                    else:
                        constraints.append(f"({begin[0]}..{end[0]})")
                elif begin:
                    if begin[1]:
                        constraints.append(f"[{begin[0]}..]")
                    else:
                        constraints.append(f"({begin[0]}..]")
                elif end:
                    if end[1]:
                        constraints.append(f"[..{end[0]}]")
                    else:
                        constraints.append(f"[..{end[0]})")

            begin = None
            end = None
            for key, val in sorted(specs, key=lambda x: x[1]):
                # if begin, then it is already in a range
                if key == "==":
                    if begin and end:
                        add_range(begin, end)
                        begin = None
                        end = None
                    if not begin:
                        constraints.append(f"[{val}]")

                if key == ">":
                    if end:
                        add_range(begin, end)
                        end = None
                        begin = None
                    if not begin:
                        begin = (val, False)
                if key == ">=":
                    if end:
                        add_range(begin, end)
                        begin = None
                        end = None
                    if not begin:
                        begin = (val, True)

                if key == "<":
                    end = (val, False)
                if key == "<=":
                    end = (val, True)
            add_range(begin, end)

            res.append({"forge": "PyPI", "product": req.name, "constraints": constraints})

        return res

    def get_modules(self):
        mods = {}

        for modname, module in self.internal_mods.items():
            name = self.to_uri(modname, external=False)
            filename = module["filename"]
            namespaces = module["methods"]

            mods[name] = {
                "SourceFileName": filename,
                "namespaces": [],
                "superClasses": {}
            }

            for namespace in namespaces:
                namespace_uri = self.to_uri(modname, namespace, external=False)

                unique = self.get_unique_and_increment()
                mods[name]["namespaces"].append([namespace_uri, unique])
                self.namespace_map[namespace_uri] = unique

            for cls_name, cls in self.classes.items():
                if not cls["module"] == modname:
                    continue

                cls_uri = self.to_uri(modname, cls_name, external=False)
                mods[name]["superClasses"][cls_uri] = []
                for parent in cls["mro"]:
                    if self.classes.get(parent):
                        parent_uri = self.to_uri(self.classes[parent]["module"],
                            parent, external=False)
                    else:
                        # TODO-HACK: this instance should not know anything about utils.constants
                        parent_name = utils.join_ns(utils.constants.EXT_NAME, parent)
                        parent_uri = self.to_uri(utils.constants.EXT_NAME, parent_name, external=True)
                    if not parent_uri == cls_uri:
                        mods[name]["superClasses"][cls_uri].append(parent_uri)
        return mods

    def create_namespaces_map(self):
        namespaces_maps = [{}, {}]
        for res, hmap in zip(namespaces_maps, [self.internal_mods, self.external_mods]):
            for mod in hmap:
                for namespace in hmap[mod]["methods"]:
                    res[namespace] = mod

        return namespaces_maps

    def get_graph(self):
        graph = []

        internal, external = self.create_namespaces_map()

        for src, dst in self.edges:
            uris = []
            for node in [src, dst]:
                if node in internal:
                    mod = internal[node]
                    uri = self.to_uri(mod, node, external=False)
                    uris.append(self.namespace_map.get(uri, uri))
                elif node in external:
                    mod = external[node]
                    uris.append(self.to_uri(mod, node, external=True))

            if len(uris) == 2:
                graph.append([
                    uris[0],
                    uris[1]
                ])
        return graph

    def generate(self):
        return {
            "product": self.product,
            "forge": self.forge,
            "depset": self.find_dependencies(self.package),
            "version": self.version,
            "timestamp": self.timestamp,
            "modules": self.get_modules(),
            "graph": self.get_graph()
        }

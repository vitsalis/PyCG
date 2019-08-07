import symtable
import os
import json

from pycg.representations import Scope

def log(msg):
    print (msg)

def analyze_scopes(modulename, contents, filename):
    scopes = {}
    # Analyze scopes of the current module
    # Fills up self.scopes recursivelly in the format
    # "<scope_namespace>" -> <Scope object>
    def process(parent_ns, table, parent_defs):
        sc = Scope(table, parent_ns, parent_defs)
        scopes[sc.ns] = sc
        for t in table.get_children():
            # Fill up Scope.defs with the types of children
            def_type = t.get_type()
            if def_type == "function":
                nstype = Scope.FUNCTION_DEF
            elif def_type == "class":
                nstype = Scope.CLASS_DEF
            elif def_type == "import":
                nstype = Scope.IMPORT_DEF
            else:
                nstype = Scope.UNKNOWN
            sc.add_def(t.get_name(), nstype, "%s.%s" % (sc.ns, t.get_name()))
            process(sc.ns, t, sc.defs)

    process(modulename, symtable.symtable(contents, filename, compile_type="exec"), {})
    return scopes

def to_mod_name(name):
    name = name.replace("/", ".")
    name = name[:-3]
    return name

def discover_locals(dirname):
    # Recursivelly determine all modules accessible from filename
    local_modules = {}

    def process(dirname, modname):
        for name in os.listdir(dirname if dirname else "."):
            fullname = os.path.join(dirname, name)
            mod = os.path.join(modname, name)
            if os.path.isfile(fullname) and name.endswith(".py"):
                local_modules[to_mod_name(mod)] = fullname
            if os.path.isdir(fullname) and os.path.exists(os.path.join(fullname, "__init__.py")):
                process(fullname, mod)
    process(dirname, "")

    return local_modules

def parent_ns(ns):
    return ".".join(ns.split(".")[:-1])

def transitive_closure(track):
    for t1 in track:
        for t2 in track:
            for t3 in track:
                if t3 in track[t2] or (t1 in track[t1] and t3 in track[t1]):
                    track[t2] = list(set(track[t2] + track[t3]))

    return track

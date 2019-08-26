import symtable
import os
import json

from pycg.representations import Scope

def log(msg):
    print (msg)

def analyze_scopes(modulename, contents, filename):
    """
    Analyze the scopes of the given module.
    Gets the symbol table of the module and
    recursivelly iterates all functions defined
    in the module to find the names they define.
    Fills a dictionary in the form
    "<scope_namespace>" -> <Scope object>
    """
    scopes = {}
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
    """
    Gets a file path and converts it to a module name
    """
    name = name.replace("/", ".")
    name = name[:-3]
    return name

def discover_locals(dirname):
    """
    Recursivelly determine all modules accessible from filename
    """
    local_modules = {}

    def process(dirname, modname):
        for name in os.listdir(dirname if dirname else "."):
            fullname = os.path.join(dirname, name)
            mod = os.path.join(modname, name)
            if os.path.isfile(fullname) and name.endswith(".py"):
                local_modules[to_mod_name(mod)] = fullname
            # if it has an init file then it is a submodule
            if os.path.isdir(fullname) and os.path.exists(os.path.join(fullname, "__init__.py")):
                process(fullname, mod)
    process(dirname, "")

    return local_modules

def parent_ns(ns):
    return ".".join(ns.split(".")[:-1])

def backwards_tracking(track):
    """
    Resolve backwards tracking information
    """
    tracking = {}
    for t in track:
        tracking[t] = track[t]
        prefix = t.split(".")
        suffix = []
        while len(prefix) != 1:
            suffix = [prefix[-1]] + suffix
            prefix = prefix[:-1]
            prefixstr = ".".join(prefix)
            suffixstr = ".".join(suffix)
            if prefixstr in track:
                for name in track[prefixstr]:
                    tracking[name + "." + suffixstr] = track[t]

    return tracking

def transitive_closure(track):
    """
    Perform a transitive closure on the given dictionary
    """
    for t1 in track:
        for t2 in track:
            for t3 in track:
                if t3 in track[t2] or (t1 in track[t1] and t3 in track[t1]):
                    track[t2] = list(set(track[t2] + track[t3]))

    return track

from programs import analysed, call_graph, callees

PLUGINS = {
    "plugins/__init__.py": "",
    "plugins/alpha.py": "def run(): pass\n",
    "plugins/beta.py": "def run(): pass\n",
}


def test_import_module_with_a_literal_imports_that_module(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            **PLUGINS,
            "main.py": """
import importlib
import importlib as loader
from importlib import import_module
importlib.import_module("plugins.alpha").run()
loader.import_module("plugins.alpha").run()
import_module("plugins.alpha").run()
""",
        },
    )

    assert callees(graph, "main") == ["importlib.import_module", "plugins.alpha.run"]
    assert "plugins" in graph
    assert "plugins.beta" not in graph


def test_dunder_import_gives_the_top_package_without_fromlist(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "shop/__init__.py": "",
            "shop/cart.py": "def total(): pass\n",
            "main.py": """
package = __import__("shop.cart")
package.cart.total()
leaf = __import__("shop.cart", fromlist=["total"])
leaf.total()
""",
        },
    )

    assert callees(graph, "main") == ["<builtin>.__import__", "shop.cart.total"]


def test_an_outside_module(tmp_path):
    graph = call_graph(
        tmp_path,
        {"main.py": 'import importlib\nimportlib.import_module("json").dumps(1)\n'},
    )

    assert callees(graph, "main") == ["importlib.import_module", "json.dumps"]


def test_a_name_that_is_no_literal_imports_nothing(tmp_path):
    generator = analysed(
        tmp_path,
        {
            **PLUGINS,
            "main.py": """
import importlib
name = "plugins.alpha"
importlib.import_module(name).run()
importlib.import_module("plugins." + "beta").run()
""",
        },
    )

    graph = generator.output()
    assert "plugins.alpha" not in graph
    assert "plugins.beta" not in graph
    assert callees(graph, "main") == ["importlib.import_module"]


def test_a_function_named_import_module_elsewhere_is_no_import(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            **PLUGINS,
            "main.py": """
def import_module(name): pass
import_module("plugins.alpha")
""",
        },
    )

    assert "plugins.alpha" not in graph


def test_a_parameter_named_import_module_is_no_import(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": """
from importlib import import_module
class Local:
    def run(self): pass
def local_loader(name):
    return Local()
def load(import_module):
    import_module("json").run()
load(local_loader)
""",
        },
    )

    assert callees(graph, "main.load") == ["main.Local.run", "main.local_loader"]


def test_an_empty_fromlist_gives_the_top_package(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "shop/__init__.py": "",
            "shop/cart.py": "def total(): pass\n",
            "main.py": """
__import__("shop.cart", fromlist=()).cart.total()
__import__("shop.cart", fromlist=[]).cart.total()
__import__("shop.cart", None, None, ()).cart.total()
""",
        },
    )

    assert callees(graph, "main") == ["<builtin>.__import__", "shop.cart.total"]


def test_limit_a_relative_literal_import_is_not_followed(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            **PLUGINS,
            "main.py": """
from importlib import import_module
import_module(".alpha", "plugins").run()
""",
        },
    )

    assert "plugins.alpha" not in graph


def test_only_a_module_builtin_or_frozen_in_every_python_wins_over_a_file(tmp_path):
    graph = call_graph(
        tmp_path,
        {
            "main.py": "import os\nimport math\nos.getcwd()\nmath.floor(1.5)\n",
            "os.py": "def helper(): pass\ndef getcwd():\n    helper()\n",
            "math.py": "def helper(): pass\ndef floor(x):\n    helper()\n",
        },
    )

    assert callees(graph, "math.floor") == ["math.helper"]
    assert callees(graph, "os.getcwd") == []

pycg - Python Call Graphs
=================================

pycg is a tool that generates call graphs for Python code using static
analysis. Given the entry point of a Python module pycg:
- Traverses the AST of the given code using Python's `ast` module.
- Automatically discovers all imported modules using Python's `importlib`
  module and further analyzes them.
- Keeps name tracking information, meaning that all assignments of functions to
  variables, functions passed as parameters or functions returned are tracked
  and included in the call graph.

Test Suite
==========

A test suite is provided containg 80+ unique snippets of Python code testing
more than simple static features.

This test suite is provided so it can help future users and maintainers
of pycg or other call graph generation tools test the coverage of their
implementation in a complete test suite of Python snippets.

New snippets are added and whenever a bug is encountered regression tests
are implemented.

Installation
============

pycg only uses stdlib modules.

```
python{,3} setup.py install
```

Usage
=====

```
pycg <entry_point>
```

The entry point might be a Python file or the package to be analyzed.

When analyzing packages it is preferred to provide the path to the package
instead of the Python file, since pycg will discover the `__main__.py` file
itself.

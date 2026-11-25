The `main` module imports the `nested.to_import` module with `from nested import to_import`. That module imports the top-level module `to_import2` with an absolute import, `import to_import2`.
`main`, `nested.to_import` and `to_import2` each define a function `func`. No function is called.

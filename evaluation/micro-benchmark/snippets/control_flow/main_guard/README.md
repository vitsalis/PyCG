An `if __name__ == "__main__":` block runs in the script and not in the imported module. The call `selftest()` in `helper.py`, and the call `run()` in `selftest`, never run.
Precision: there are no edges `helper -> helper.selftest` and `helper.selftest -> helper.run`.

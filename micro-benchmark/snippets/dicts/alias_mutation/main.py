def func1():
    pass

d = {}
alias = d
alias["run"] = func1
d["run"]()

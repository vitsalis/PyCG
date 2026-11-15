Two instances of one class store different functions in the same attribute,
and only one instance calls it. An analysis that merges the attributes of all
instances reports the edge `main.Button.click -> main.load`, which must not
appear.

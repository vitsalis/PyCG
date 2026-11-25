Two unrelated classes define a method with the same name, and only one
instance reaches the call. An analysis that resolves methods by name reports
the edge `main.talk -> main.Robot.speak`, which must not appear.

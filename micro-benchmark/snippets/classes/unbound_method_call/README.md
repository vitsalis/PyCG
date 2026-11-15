A method is called through the class with an explicit instance
(`Base.greet(child)`). The receiver is a `Child`, but the method is looked up on
`Base`: the edge `main -> main.Child.greet` must not appear.

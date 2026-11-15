The two-argument form `super(Middle, self)` starts the lookup after `Middle` in
the MRO, so it skips `Middle.save`. The edge
`main.Child.save -> main.Middle.save` must not appear.

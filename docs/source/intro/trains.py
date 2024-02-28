import pyirk as p

# pyirk boilerplate
__URI__ = "irk:/examples/0.2/trains"
keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)

# create the train item
I1 = p.create_item(
    R1__has_label="train",
    R2__has_description="form of rail transport consisting of a series of connected vehicles",
)

# create the mode of transport item
I2 = p.create_item(
    R1__has_label="mode of transport",
    R2__has_description="different ways of transportation such as air, water, and land transport",
)

# add `is instance of` relation between them
I1.set_relation(p.R4["is instance of"], I2["mode of transport"])

# create the locomotive and the railroad car
I3 = p.create_item(
    R1__has_label="locomotive",
    R2__has_description="railway vehicle that provides the motive power for a train",
    R5__is_part_of=I1["train"]
)
I4 = p.create_item(
    R1__has_label="railroad car",
    R2__has_description="vehicle used for carrying cargo or passengers on rail transport system",
    R5__is_part_of=I1["train"]
)

# visualize the graph
with open("./trains.svg", "w") as f:
    f.write(p.visualize_entity(I1.uri))

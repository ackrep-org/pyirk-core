import pyirk as p

__URI__ = "irk:/examples/0.2/trains"
keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)

# # data store on module level
# ds = {}

I1 = p.create_item(
    R1__has_label="mode of transport",
    R2__has_description="different ways of transportation such as air, water, and land transport",
)

I2 = p.create_item(
    R1__has_label="train",
    R2__has_description="form of rail transport consisting of a series of connected vehicles",
    R4__is_instance_of=I1["mode of transport"],
)

# Note: this is not the real module for this URI it is an autogenerated subset for testing


import pyerk as p


__URI__ =  "erk:/ocse/0.2/agents"

keymanager = p.KeyManager(keyseed=1239)
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)

insert_entities = [
I2746["Rudolf Kalman"],
R1833["has employer"],
]

p.end_mod()

# Note: this is not the real module for this URI it is an autogenerated subset for testing

from typing import Union
import pyerk as p

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception  # noqa

ag = p.erkloader.load_mod_from_path("./agents1.py", prefix="ag")

__URI__ = "erk:/ocse/0.2/math"

keymanager = p.KeyManager()
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)

insert_entities = [
I4895["mathematical operator"],
raw__I4895["mathematical operator"].add_method(p.create_evaluated_mapping, "_custom_call"),
I9923["scalar field"],
I9841["vector field"],
I4236["mathematical expression"],
I1060["general function"],
I1063["scalar function"],
I4237["monovariate rational function"],
raw__I4237["monovariate rational function"].add_method(p.create_evaluated_mapping, "_custom_call"),
I4239["abstract monovariate polynomial"],
R3326["has dimension"],
I5166["vector space"],
I5167["state space"],
R5405["has associated state space"],
I1168["point in state space"],
I9904["matrix"],
I9905["zero matrix"],
R5939["has column number"],
R5938["has row number"],
I5177["matmul"],
I5000["scalar zero"],
R3033["has type of elements"],
I8133["field of numbers"],
I2738["field of complex numbers"],
I5807["sign"],
I9906["square matrix"],
I9907["definition of square matrix"],
with__I9907.scope("setting"),
with__I9907.scope("premise"),
with__I9907.scope("assertion"),
I6259["sequence"],
I9739["finite scalar sequence"],
I4240["matrix polynomial"],
R5940["has characteristic polynomial"],
I3058["coefficients of characteristic polynomial"],
I3749["Cayley-Hamilton theorem"],
with__I3749["Cayley-Hamilton theorem"].scope("setting"),
# this theorem has no premise
with__I3749["Cayley-Hamilton theorem"].scope("assertion"),
I5030["variable"],
R8736["depends polyonomially on"],
I1935["polynomial matrix"],
I7765["scalar mathematical object"],
I5359["determinant"],
def__I5359_cc_pp,
raw__I5359["determinant"].add_method(I5359_cc_pp, "_custom_call_post_process"),
I6324["canonical first order monic polynomial matrix"],
def__I6324_cc_pp,
raw__I6324["canonical first order monic polynomial matrix"].add_method(I6324_cc_pp, "_custom_call_post_process"),
I1195["integer range"],
R1616["has start value"],
R1617["has stop value"],
R1618["has step value"],
I6012["integer range element"],
class__IntegerRangeElement,
I3240["matrix element"],
]

p.end_mod()

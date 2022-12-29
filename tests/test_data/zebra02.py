"""
created: 2022-12-25 18:35:54
original author Carsten Knoll <firstname.lastname@tu-dresden.de>

This module aims to model information with a similar structure to that of the logical "zebra puzzle" by A. Einstein.
It serves to explore the solution of the full puzzle.
See https://en.wikipedia.org/wiki/Zebra_Puzzle
"""


import pyerk as p

zb = p.erkloader.load_mod_from_path("./zebra_base_data.py", prefix="zb")


__URI__ = "erk:/ocse/0.2/zebra02"

keymanager = p.KeyManager(keyseed=1438)
p.register_mod(__URI__, keymanager)

p.start_mod(__URI__)


# ###############################################################################

"""
All Hints (from https://en.wikipedia.org/wiki/Zebra_Puzzle):
    
1. There are five houses.
2. The Englishman lives in the red house.
3. The Spaniard owns the dog.
4. Coffee is drunk in the green house.
5. The Ukrainian drinks tea.
6. The green house is immediately to the right (from perspective of the viewer) of the ivory house.
7. The Old Gold smoker owns snails.
8. Kools are smoked in the yellow house.
9. Milk is drunk in the middle house.
10. The Norwegian lives in the first house.
11. The man who smokes Chesterfields lives in the house next to the man with the fox.
12. Kools are smoked in the house next to the house where the horse is kept.
13. The Lucky Strike smoker drinks orange juice.
14. The Japanese smokes Parliaments.
15. The Norwegian lives next to the blue house.

"""

# ###############################################################################

# model hint by hint

# 1. There are five houses. ✓
# 2. The Englishman lives in the red house.

zb.I4037["Englishman"].set_relation("zb__R8098__has_house_color", zb.I5209["red"])

# 3. The Spaniard owns the dog.

zb.I2552["Spaniard"].set_relation("zb__R5611__owns", zb.I2183["dog"])

# 4. Coffee is drunk in the green house.


"""

I3606
I9412
I8499
I6258
"""


# ###############################################################################


p.end_mod()


"""
key reservoir created with: `pyerk -l zebra01.py ag -nk 100`
supposed keys:
    
R2353
R2850
    
I9803
I2835
I9122
I1055
I5109
I4872
I8139
I8768
I6020
I2693
I2183
I1437
I8809
I6448
I7582
I4735
I4785
I7258
I1933
I4892
I2911
I4715
I6147
I7536
I9491
I7825
I6844
I6970
I1835
I3560
I9209
I5644
I1873
I8554
I2406
I3914
I9756
I1420
I9987
I4269
I3798
I7141
I3852
I3536
I8232
I1321
I6487
I3724
I6615
I6642
I8100
I5157
I2116
I2231
I8503
I2831
I9596
I5390
I7359
I8782
I4296
I7097
I6415
I4738
I1897
I5216
I4466
I3016
I9202
`

"""

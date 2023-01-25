"""
created: 2022-12-25 18:35:54
original author Carsten Knoll <firstname.lastname@tu-dresden.de>

This module aims to model information with a similar structure to that of the logical "zebra puzzle" by A. Einstein.
It serves to explore the solution of the full puzzle.
See https://en.wikipedia.org/wiki/Zebra_Puzzle
"""


import pyerk as p

zb = p.erkloader.load_mod_from_path("./zebra_base_data.py", prefix="zb", reuse_loaded=True)
zr = p.erkloader.load_mod_from_path("./zebra_puzzle_rules.py", prefix="zr", reuse_loaded=True)


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

person1 = p.instance_of(zb.I7435["human"])
person1.set_relation("R57__is_placeholder", True)
person1.set_relation("zb__R8216__drinks", zb.I4850["coffee"])
person1.set_relation("zb__R8098__has_house_color", zb.I8065["green"])

# 5. The Ukrainian drinks tea.

zb.I3132["Ukrainian"].set_relation("zb__R8216__drinks", zb.I6756["tea"])

# 6. The green house is immediately to the right (from perspective of the viewer) of the ivory house.

person2 = p.instance_of(zb.I7435["human"])
person2.set_relation("R57__is_placeholder", True)
person2.set_relation("zb__R8098__has_house_color", zb.I8065["green"])

person3 = p.instance_of(zb.I7435["human"])
person3.set_relation("R57__is_placeholder", True)
person3.set_relation("zb__R8098__has_house_color", zb.I7612["ivory"])

person2.set_relation("zb__R2353__lives_immediately_right_of", person3)

# 7. The Old Gold smoker owns snails.

person4 = p.instance_of(zb.I7435["human"])
person4.set_relation("R57__is_placeholder", True)
person4.set_relation("zb__R8592__smokes", zb.I1055["Old Gold"])
person4.set_relation("zb__R5611__owns", zb.I2693["snails"])

# 8. Kools are smoked in the yellow house.

person5 = p.instance_of(zb.I7435["human"])
person5.set_relation("R57__is_placeholder", True)
person5.set_relation("zb__R8592__smokes", zb.I2835["Kools"])
person5.set_relation("zb__R8098__has_house_color", zb.I4118["yellow"])

# 9. Milk is drunk in the middle house. -> index = 3

person6 = p.instance_of(zb.I7435["human"])
person6.set_relation("R57__is_placeholder", True)
person6.set_relation("zb__R8216__drinks", zb.I9779["milk"])
person6.set_relation("zb__R9040__lives_in_numbered_house", zb.I4735["house 3"])

# 10. The Norwegian lives in the first house.

zb.I9848.set_relation("zb__R9040__lives_in_numbered_house", zb.I6448["house 1"])

# 11. The man who smokes Chesterfields lives in the house next to the man with the fox.

person7 = p.instance_of(zb.I7435["human"])
person7.set_relation("R57__is_placeholder", True)
person7.set_relation("zb__R8592__smokes", zb.I9122["Chesterfield"])

person8 = p.instance_of(zb.I7435["human"])
person8.set_relation("R57__is_placeholder", True)
person8.set_relation("zb__R5611__owns", zb.I8768["fox"])

person7.set_relation("zb__R3606__lives_next_to", person8)

# 12. Kools are smoked in the house next to the house where the horse is kept.

person9 = p.instance_of(zb.I7435["human"])
person9.set_relation("R57__is_placeholder", True)
person9.set_relation("zb__R8592__smokes", zb.I2835["Kools"])

person10 = p.instance_of(zb.I7435["human"])
person10.set_relation("R57__is_placeholder", True)
person10.set_relation("zb__R5611__owns", zb.I6020["horse"])

person9.set_relation("zb__R3606__lives_next_to", person10)

# 13. The Lucky Strike smoker drinks orange juice.

person11 = p.instance_of(zb.I7435["human"])
person11.set_relation("R57__is_placeholder", True)
person11.set_relation("zb__R8592__smokes", zb.I5109["Lucky Strike"])
person11.set_relation("zb__R8216__drinks", zb.I6014["orange juice"])

# 14. The Japanese smokes Parliaments.

zb.I5931["Japanese"].set_relation("zb__R8592__smokes", zb.I4872["Parliaments"])

# 15. The Norwegian lives next to the blue house.

person12 = p.instance_of(zb.I7435["human"])
person12.set_relation("R57__is_placeholder", True)
person12.set_relation("zb__R8098__has_house_color", zb.I1497["blue"])

zb.I9848["Norwegian"].set_relation("zb__R3606__lives_next_to", person12)

"""


I9412
I8499
I6258
"""


# ###############################################################################


p.end_mod()


"""
key reservoir created with: `pyerk -l zebra01.py ag -nk 100`
supposed keys:





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

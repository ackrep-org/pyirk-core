# Note: this is not the real module for this URI it is an autogenerated subset for testing


import pyirk as p


__URI__ =  "irk:/ocse/0.2/agents"

keymanager = p.KeyManager(keyseed=1239)
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)

start_time = p.QualifierFactory(p.R48["has start time"])
end_time = p.QualifierFactory(p.R49["has end time"])


insert_entities = [
    def__create_person,
    I7435["human"],
    R7781["has family name"],
    R7782["has given name"],
    R3474["has ORCID"],
    R3475["has DBLP author ID"],
    I2746["Rudolf Kalman"],
    R1833["has employer"],
    I1342["academic institution"],
    I9942["Stanford University"],
    I7301["ETH Zürich"],
    raw__I2746["Rudolf Kalman"].set_relation(R1833["has employer"], I9942["Stanford University"], qualifiers=[start_time("1964"), end_time("1971")]),
    raw__I2746["Rudolf Kalman"].set_relation(R1833["has employer"], I7301["ETH Zürich"], qualifiers=[start_time("1973"), end_time("1997")]),
    I4853["Sophus Lie"],
    R6876["is named after"],
    I2151["Aleksandr Lyapunov"],
]

p.end_mod()

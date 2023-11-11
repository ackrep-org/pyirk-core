# Note: this is not the real module for this URI it is an autogenerated subset for testing


import pyerk as p


__URI__ =  "erk:/ocse/0.2/agents"

keymanager = p.KeyManager(keyseed=1239)
p.register_mod(__URI__, keymanager)
p.start_mod(__URI__)

def create_person(given_name: str, family_name: str, r2: str, r33=None, r3474=None, r3475=None):
    """
    This is a convenience function that simplifies the creation of items for humans
    """
    item_key = p.get_key_str_by_inspection()

    r1 = f"{given_name} {family_name}"
    item: p.Item  = p.create_item(
        item_key,
        R1__has_label=r1,
        R2__has_description=r2,
        R4__is_instance_of=I7435["human"],
        R7781__has_family_name=family_name,
        R7782__has_given_name=given_name,
    )

    if r33:
        assert isinstance(r33, str)
        item.set_relation(p.R33["has corresponding wikidata entity"], r33)
    if r3474:
        assert isinstance(r3474, str)
        item.set_relation(R3474["has ORCID"], r3474)
    if r3475:
        assert isinstance(r3475, str)
        item.set_relation(R3475["has DBLP author ID"], r3475)

    return item

I7435 = p.create_item(
    R1__has_label="human",
    R2__has_description="human being",
    R4__is_instance_of=p.I2["Metaclass"],
    R33__has_corresponding_wikidata_entity="https://www.wikidata.org/entity/Q5",
)

R7781 = p.create_relation(
    R1__has_label="has family name",
    R2__has_description="part of the full name of a person",
    R33__has_corresponding_wikidata_entity="https://www.wikidata.org/wiki/Property:P734",
)

R7782 = p.create_relation(
    R1__has_label="has given name",
    R2__has_description="first name or another given name of this person",
    R18__has_usage_hint=[
        "this relation is non-functional, i.e. a person can have multiple given names; order matters",
        "if given name is unknown, it is acceptable to use initials here",
    ],
    R33__has_corresponding_wikidata_entity="https://www.wikidata.org/wiki/Property:P735",
)

R3474 = p.create_relation(
    R1__has_label="has ORCID",
    R2__has_description="specifies the orcid of a researcher",
    R18__has_usage_hint="This can be used if no wikidata entry is yet available",
    R33__has_corresponding_wikidata_entity="https://www.wikidata.org/wiki/Property:P496",
)

R3475 = p.create_relation(
    R1__has_label="has DBLP author ID",
    R2__has_description="specifies the DBLP author ID of a researcher",
    R18__has_usage_hint="This can be used if neither wikidata nor ORCID is yet available",
    R33__has_corresponding_wikidata_entity="https://www.wikidata.org/wiki/Property:P2456",
)

I2746 = create_person("Rudolf", "Kalman", "electrical engineer and mathematician")

R1833 = p.create_relation(
    R1__has_label="has employer",
    R2__has_description="specifies for which entity (organisation/person) the subject works",
    R33__has_corresponding_wikidata_entity="https://www.wikidata.org/entity/P108",
)

I4853 = create_person("Sophus", "Lie", "mathematician", r33="https://www.wikidata.org/wiki/Q30769")

R6876 = p.create_relation(
    R1__has_label="is named after",
    R2__has_description="specifies that the subject is an eponym named after the object",
    R33__has_corresponding_wikidata_entity="https://www.wikidata.org/entity/P138",
)


p.end_mod()

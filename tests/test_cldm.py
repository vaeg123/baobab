from baobab.core.ontology.cldm import RootObject, UNIVERSAL_PROPERTIES, RELATION_TYPES


def test_cldm_has_eight_root_objects():
    assert len(RootObject) == 8


def test_cldm_has_fifteen_universal_properties():
    assert len(UNIVERSAL_PROPERTIES) == 15


def test_relation_types_defined():
    assert "abrogated_by" in RELATION_TYPES
    assert "triggers" in RELATION_TYPES

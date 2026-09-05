"""The act scorer (design §2.5, §6.1): strict on the act, honest about the wrong value."""

from atlas0 import acts


def test_parse_reads_exactly_one_act():
    assert acts.parse(" ANSWER mod_lane").kind == "ANSWER"
    assert acts.parse("ANSWER mod_lane\nQ: next").values == ("mod_lane",)
    assert acts.parse("CANDIDATES a_b, c_d").values == ("a_b", "c_d")
    assert acts.parse("UNDEFINED").kind == "UNDEFINED"
    assert acts.parse("UNKNOWN").kind == "UNKNOWN"


def test_hedges_and_junk_are_malformed_not_undefined():
    for text in ("", "UNDEFINED maybe", "I think ANSWER x", "ANSWER two words", "CANDIDATES", "CANDIDATES a, a",
                 "answer mod_lane", "ANSWER", "UNKNOWN mod_x", "maybe UNDEFINED"):
        assert acts.parse(text).kind == "malformed", text


def test_grade_places_each_act_in_one_column():
    item = {"gold": ["mod_a"], "gold_trained": ["mod_a"], "sibling": "mod_b"}
    g = lambda t: acts.grade(acts.parse(t), item)
    assert g("ANSWER mod_a") == acts.Grade("ANSWER-correct", memorised=True)
    assert g("ANSWER mod_b") == acts.Grade("ANSWER-wrong", "sibling")
    assert g("ANSWER mod_z") == acts.Grade("ANSWER-wrong", "other")
    assert g("CANDIDATES mod_z, mod_a") == acts.Grade("CANDIDATES-with", "2", memorised=True)
    assert g("CANDIDATES mod_z") == acts.Grade("CANDIDATES-without")
    assert g("UNDEFINED") == acts.Grade("UNDEFINED")
    assert g("UNKNOWN") == acts.Grade("UNKNOWN")
    assert g("???") == acts.Grade("malformed")
    absent = {"gold": [], "gold_trained": [], "sibling": "mod_b"}
    assert acts.grade(acts.parse("ANSWER mod_b"), absent) == acts.Grade("ANSWER-wrong", "sibling")
    assert acts.grade(acts.parse("UNDEFINED"), absent).column == "UNDEFINED"


def test_confusion_matrix_rows_and_extras():
    items = [
        {"id": "1", "class": "dense-real", "exposure": "n/a", "gold": ["m1"], "gold_trained": [], "sibling": "m2"},
        {"id": "2", "class": "sparse-real", "exposure": "n/a", "gold": ["m1"], "gold_trained": [], "sibling": "m2"},
        {"id": "3", "class": "absent-near", "exposure": "held-out", "gold": [], "gold_trained": [], "sibling": "m2"},
        {"id": "4", "class": "absent-near", "exposure": "trained", "gold": [], "gold_trained": [], "sibling": "m2"},
        {"id": "5", "class": "absent-far", "exposure": "held-out", "gold": [], "gold_trained": [], "sibling": "m2"},
    ]
    outputs = {"1": "ANSWER m1", "2": "UNDEFINED", "3": "ANSWER m2", "4": "UNDEFINED"}
    m = acts.confusion(items, outputs)
    assert m["missing"] == 1
    assert m["rows"]["dense-real"]["ANSWER-correct"] == 1
    assert m["rows"]["sparse-real"]["UNDEFINED"] == 1
    assert m["rows"]["absent-near/held-out"]["ANSWER-wrong"] == 1 and m["extra"]["absent-near/held-out"]["wrong-sibling"] == 1
    assert m["rows"]["absent-near/trained"]["UNDEFINED"] == 1
    text = acts.render(m)
    assert "absent-near/held-out" in text and "missing outputs: 1" in text

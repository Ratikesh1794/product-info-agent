import pytest

from app.services.catalog import Status, get_catalog, normalize_model


@pytest.fixture(scope="module")
def cat():
    return get_catalog()


def test_loads_every_row(cat):
    assert len(cat.products) == 2261


def test_model_lookup_tolerates_case_and_punctuation(cat):
    assert normalize_model("gsr18v 535cn") == "GSR18V535CN"
    assert cat.get("gsr18v 535cn").model_number == "GSR18V-535CN"
    assert cat.get(cat.products[0].sku) is cat.products[0]
    assert cat.get("NOPE-123") is None


def test_suggest_for_typo(cat):
    assert "GSR18V-535CB25" in cat.suggest("GSR18V-535CB52")


def test_pipe_fields_split(cat):
    p = cat.get("GBA18V20")
    assert p.key_features[0] == "Fits all Bosch 18V tools and chargers"
    assert p.whats_in_the_box == ["GBA18V20 battery"]


def test_torque_mirrored_across_units(cat):
    # Q2: impact wrench torque is stored in ft-lbs, drills in in-lbs; both must be filterable either way.
    wrench = next(p for p in cat.products if "max_fastening_torque_ft_lbs" in p.specs)
    assert wrench.specs["max_fastening_torque_in_lbs"] == wrench.specs["max_fastening_torque_ft_lbs"] * 12
    drill = next(p for p in cat.products if "max_torque_in_lbs" in p.specs)
    assert drill.specs["max_torque_ft_lbs"] == round(drill.specs["max_torque_in_lbs"] / 12, 1)


def test_replacements(cat):
    disc = [p for p in cat.products if p.status == Status.DISCONTINUED]
    with_repl = [p for p in disc if cat.replacement_for(p)]
    assert (len(disc), len(with_repl)) == (217, 156)  # 61 have no replacement: agent must say so
    assert len(cat.audit()["discontinued_no_replacement"]) == 61


def test_jacket_variants_are_skus(cat):
    # Q7: size/fit live in specs; women's medium 18V exists.
    hits = [p for p in cat.products if p.specs.get("fit") == "Women's" and p.specs.get("size") == "M" and p.voltage_v == 18]
    assert {p.model_number for p in hits} >= {"PSJ18WB-M"}


def test_spec_key_discovery(cat):
    keys = cat.spec_keys("Measuring Tools")
    assert "working_range_ft" in keys and "beam_color" in keys


def test_audit_flags_name_model_mismatch(cat):
    assert "GLL332GCKB" in cat.audit()["name_model_mismatch"]

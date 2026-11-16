"""One test per assignment scenario, plus the 'don't know' paths. No LLM involved."""

import json

from app.services.catalog import get_catalog
from app.services.tools import (
    CompareArgs,
    CompatArgs,
    DescribeArgs,
    ModelArgs,
    SearchArgs,
    SpecFilter,
    check_availability,
    compare_products,
    describe_catalog,
    find_compatible,
    get_product,
    openai_tools,
    run_tool,
    search_products,
)

cat = get_catalog()
models = lambda r: {p["model_number"] for p in r["products"]}


def test_q1_compare_same_tool_different_kit():
    r = compare_products(CompareArgs(model_numbers=["GSR18V-535CN", "gsr18v535cb25"]), cat)
    assert {"msrp_usd", "whats_in_the_box", "battery_included", "specs.kit_type"} <= r["different"].keys()
    assert r["same"]["specs.max_torque_in_lbs"] == 485  # identical tool


def test_q2_impact_wrench_torque_and_price():
    def run(key):
        return search_products(SearchArgs(query="impact wrench", voltage_v=18, max_price=300,
                                          spec_filters=[SpecFilter(key=key, op=">=", value=500)]), cat)
    fastening = run("max_fastening_torque_ft_lbs")
    assert models(fastening) == {"GDS18V-30CPN", "GDS18V-800CPN"}
    # the products lacking torque are the two-in-one driver/wrenches, not dedicated wrenches
    assert set(fastening["missing_spec_data"]["max_fastening_torque_ft_lbs"]) == {"Two-in-One Impact Driver/Wrench"}
    nut = run("nut_busting_torque_ft_lbs")
    assert {"GDS18V-75N", "GDS18V-55N"} <= models(nut)
    alt = fastening["also_match_on_alternative_spec"]["nut_busting_torque_ft_lbs"]
    assert alt["extra_count"] == nut["total_matches"] - 2


def test_q3_starlockplus_blades_exclude_max_only():
    r = find_compatible(CompatArgs(system="StarlockPlus", query="blade", limit=25), cat)
    assert r["status_counts"] == {"Active": 30, "Temporarily Out of Stock": 2}  # matches docs/GROUND_TRUTH.md
    for p in cat.products:
        if p.model_number in models(r):
            assert not any("StarlockMax oscillating tools only" in t for t in p.compatible_with)


def test_q3_tool_interface_conflict_surfaced():
    r = find_compatible(CompatArgs(model_number="GOP12V-75N", query="blade", limit=25), cat)
    assert "Starlock" in r["matched_on"] and r["notes"]
    for p in cat.products:
        if p.model_number in models(r):
            assert any(t.startswith("Starlock,") for t in p.compatible_with)  # base-Starlock blades only


def test_q4_replacement_with_platform_change():
    r = check_availability(ModelArgs(model_number="GSB12V-535B2"), cat)
    assert r["status"] == "Discontinued" and r["replacement"]["model_number"] == "GSB18V-75CPN"
    assert any(d.startswith("voltage: 12 -> 18") for d in r["replacement"]["differences_from_original"])


def test_q4_discontinued_without_replacement():
    r = check_availability(ModelArgs(model_number="GSR18V-30B15"), cat)
    assert r["replacement"] is None and any("No replacement" in n for n in r["notes"])


def test_q5_green_laser_100ft():
    r = search_products(SearchArgs(query="laser", spec_filters=[
        SpecFilter(key="beam_color", op="==", value="Green"),
        SpecFilter(key="working_range_ft", op=">=", value=100)], limit=25), cat)
    assert r["total_matches"] > 0
    assert all(p["specs"]["beam_color"] == "Green" and p["specs"]["working_range_ft"] >= 100 for p in r["products"])
    assert r["missing_spec_data"]  # CST/berger green laser has no specs
    assert r["also_match_on_alternative_spec"]["range_with_receiver_ft"]["extra_count"] > 0  # receiver-only reach


def test_q6_where_to_buy_and_stale_coming_soon():
    assert check_availability(ModelArgs(model_number="GSR18V-535CN"), cat)["available_at"]
    soon = next(p for p in cat.products if p.status.value == "Coming Soon")
    assert any("passed" in n for n in check_availability(ModelArgs(model_number=soon.model_number), cat)["notes"])


def test_q7_womens_medium_jacket_and_missing_size():
    def run(size):
        return search_products(SearchArgs(query="heated jacket", voltage_v=18, spec_filters=[
            SpecFilter(key="fit", op="==", value="Women's"), SpecFilter(key="size", op="==", value=size)]), cat)
    assert models(run("M")) == {"PSJ18WB-M", "PSJ18WG-M"}  # vest excluded
    assert run("3XL")["total_matches"] == 0
    # live failure: page 1 of 22 jackets was all men's, model said "no women's". Facets cover all matches.
    page = search_products(SearchArgs(query="heated jacket", voltage_v=18), cat)
    assert page["showing"] < page["total_matches"] and "Women's" in page["facets_across_all_matches"]["fit"]


def test_unknown_model_suggests():
    r = get_product(ModelArgs(model_number="GSR18V-535CB52"), cat)
    assert not r["found"] and "GSR18V-535CB25" in r["did_you_mean"]


def test_describe_catalog_exposes_spec_keys():
    r = describe_catalog(DescribeArgs(subcategory="Line Lasers"), cat)
    assert "working_range_ft" in r["spec_keys"] and r["spec_keys"]["beam_color"]["examples"]


def test_wrong_args_are_errors_not_empty_results():
    # live failures: model passed a subcategory as category, and invented spec key "gender"
    r = describe_catalog(DescribeArgs(category="impact wrenches"), cat)
    assert r["product_count"] == 18  # auto-moved to subcategory
    assert search_products(SearchArgs(category="power tool"), cat)["error"] == "unknown_taxonomy"
    r = search_products(SearchArgs(query="heated jacket", spec_filters=[SpecFilter(key="gender", op="==", value="Women's")]), cat)
    assert r["error"] == "unknown_spec_key" and "fit" in r["valid_keys_for_these_products"]


def test_run_tool_validates_and_schemas_build():
    assert run_tool("compare_products", json.dumps({"model_numbers": ["X"]}))["error"] == "invalid_arguments"
    assert run_tool("nope", "{}")["error"].startswith("unknown")
    assert run_tool("get_product", '{"model_number": "GBA18V20"}')["found"]
    assert {t["function"]["name"] for t in openai_tools()} >= {"search_products", "find_compatible"}
    json.dumps(openai_tools())


def test_unknown_args_rejected_not_ignored():
    # eval failure: model sent fit/size as top-level args; they were dropped and results came back unfiltered
    r = run_tool("search_products", json.dumps({"query": "heated jacket", "fit": "Women's", "size": "M"}))
    assert r["error"] == "invalid_arguments" and {d["loc"][0] for d in r["details"]} == {"fit", "size"}


def test_zero_results_explain_which_filter_excluded_everything():
    # eval failure: compatible_with="18V" on apparel (voltage lives in voltage_v) -> 0 hits -> "doesn't exist"
    r = search_products(SearchArgs(query="heated jacket", compatible_with="18V", spec_filters=[
        SpecFilter(key="fit", op="==", value="Women's"), SpecFilter(key="size", op="==", value="M")]), cat)
    assert r["total_matches"] == 0 and r["zero_results_diagnosis"]["without compatible_with='18V'"] == 4
    genuine = search_products(SearchArgs(query="heated jacket", brand="Dremel", spec_filters=[SpecFilter(key="size", op="==", value="9XL")]), cat)
    assert "note" in genuine["zero_results_diagnosis"]


def test_zero_results_show_real_values_of_text_specs():
    # eval failure: size "Medium" when the catalog says "M" -> 0 hits, model retried until out of rounds
    r = search_products(SearchArgs(query="heated jacket", voltage_v=18, spec_filters=[
        SpecFilter(key="fit", op="==", value="Women's"), SpecFilter(key="size", op="contains", value="Medium")]), cat)
    assert r["total_matches"] == 0
    assert r["zero_results_diagnosis"]["values of size in those products"] == ["2XL", "L", "M", "S", "XL"]


def test_alternative_spec_is_also_a_note():
    r = search_products(SearchArgs(query="laser", spec_filters=[
        SpecFilter(key="beam_color", op="==", value="Green"), SpecFilter(key="working_range_ft", op=">=", value=100)]), cat)
    assert any("range_with_receiver_ft" in n for n in r["notes"])

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_product_detail_shows_source_specs_only():
    r = client.get("/api/products/gds18v-30cpn")  # case/punctuation-insensitive like the tools
    assert r.status_code == 200
    p = r.json()
    assert p["model_number"] == "GDS18V-30CPN" and p["msrp_usd"] == 279.0
    assert p["specs"]["max_fastening_torque_ft_lbs"] == 652
    assert "max_fastening_torque_in_lbs" not in p["specs"]  # derived unit mirror hidden
    assert "product_url" not in p  # fake per the brief


def test_discontinued_product_links_both_ways():
    old = client.get("/api/products/GSB12V-535B2").json()
    assert old["status"] == "Discontinued" and old["replacement"]["model_number"] == "GSB18V-75CPN"
    new = client.get("/api/products/GSB18V-75CPN").json()
    assert "GSB12V-535B2" in [r["model_number"] for r in new["replaces"]]


def test_unknown_product_404_with_suggestions():
    r = client.get("/api/products/GSR18V-535CB52")
    assert r.status_code == 404 and "GSR18V-535CB25" in r.json()["detail"]["did_you_mean"]

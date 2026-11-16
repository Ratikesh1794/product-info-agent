"""LLM-as-judge for the golden set: grades an agent reply against catalog ground truth.

The judge sees the raw catalog records (from the CSV, not from the agent's tools) for every product the case
involves and every product the reply mentions, so it can check any claim the agent made. Structured output +
temperature 0 keep grades machine-readable and as repeatable as an LLM allows.

`calibrate()` grades replies with known verdicts (planted errors + one correct answer) so a run can tell
whether the judge itself is trustworthy before its scores are used.
"""

import csv
import json
import re
from datetime import date
from pathlib import Path

from openai import OpenAI

from app.core.config import settings

DATA = Path(__file__).resolve().parents[1] / "data" / "bosch_product_catalog_mock.csv"
_rows = {r["model_number"]: r for r in csv.DictReader(DATA.open(encoding="utf-8"))}
_TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9]")

DIMENSIONS = ["correctness", "completeness", "grounding", "behaviour", "clarity"]

RUBRIC = f"""Today is {date.today().isoformat()}. You grade answers from a product assistant for a power-tools website. The assistant must answer ONLY
from the product catalog. You get the user's question, what a correct answer should contain, the catalog
records that are relevant, and the assistant's reply. Judge the reply against the catalog records, not your own
knowledge of real Bosch products. `case_facts` are authoritative totals computed from the WHOLE catalog (the
records list is only a sample): use them to check counts the reply states ("15 models", "6 more qualify").

First, list EVERY factual claim the reply makes about a product (price, status, spec value, kit contents,
compatibility, retailer, replacement, existence). For each, quote the catalog value from the records and mark
correct true/false. Check numbers digit by digit: "$199" vs a catalog price of 279.0 is incorrect. A claim
about a product with no record provided is incorrect unless the record list says otherwise.

Then score each dimension 1-5 (5 = flawless) with a one-sentence reason:
- correctness: every factual claim (model, price, status, spec, kit contents, compatibility, retailer,
  replacement) matches the catalog records. One false claim about a product caps this at 2.
- completeness: answers what was asked and includes the expected products/facts. Listing a subset of a long
  list is fine if the reply says there are more.
- grounding: no claims that the records don't support (invented specs, stock levels, links, opinions stated
  as fact). Reasonable general phrasing ("bare tool means no battery") is fine.
- behaviour: did the right thing: answered when it could; asked a clarifying question when the request named no
  product; said plainly when something isn't in the catalog or is out of scope; never guessed.
- clarity: direct answer first, concise, easy to scan, model numbers and prices where useful.

verdict = "pass" only if correctness >= 4, grounding >= 4 and behaviour >= 4. List concrete issues (empty if none)."""

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["claims", "scores", "verdict", "issues"],
    "properties": {
        # listed first so the model verifies each claim before it scores (it generates fields in order)
        "claims": {
            "type": "array",
            "items": {"type": "object", "additionalProperties": False, "required": ["claim", "catalog_value", "correct"],
                      "properties": {"claim": {"type": "string"}, "catalog_value": {"type": "string"},
                                     "correct": {"type": "boolean"}}},
        },
        "scores": {
            "type": "object",
            "additionalProperties": False,
            "required": DIMENSIONS,
            "properties": {
                d: {"type": "object", "additionalProperties": False, "required": ["score", "reason"],
                    "properties": {"score": {"type": "integer", "minimum": 1, "maximum": 5}, "reason": {"type": "string"}}}
                for d in DIMENSIONS
            },
        },
        "verdict": {"type": "string", "enum": ["pass", "fail"]},
        "issues": {"type": "array", "items": {"type": "string"}},
    },
}

_client: OpenAI | None = None


def _openai() -> OpenAI:
    global _client
    _client = _client or OpenAI(api_key=settings.openai_api_key)
    return _client


def record(model: str) -> dict:
    r = _rows[model]
    return {
        "model_number": model, "product_name": r["product_name"], "category": r["category"],
        "subcategory": r["subcategory"], "product_type": r["product_type"], "brand": r["brand"],
        "short_description": r["short_description"], "key_features": r["key_features"],
        "msrp_usd": float(r["msrp_usd"]), "status": r["status"], "replacement_model": r["replacement_model"] or None,
        "discontinued_date": r["discontinued_date"] or None, "launch_date": r["launch_date"] or None,
        "voltage_v": r["voltage_v"] or None, "battery_platform": r["battery_platform"] or None,
        "battery_included": r["battery_included"] or None, "whats_in_the_box": r["whats_in_the_box"],
        "compatible_with": r["compatible_with"], "available_at": r["available_at"],
        "avg_rating": r["avg_rating"] or None, "weight_lbs": r["weight_lbs"] or None,
        "dimensions_in": r["dimensions_in"] or None, "technical_specs": json.loads(r["technical_specs"] or "{}"),
    }


def _expectation(case: dict) -> str:
    if case["expect"] == "clarify":
        return "The request names no product. A correct reply asks which product the user means and states no product facts."
    if case["expect"] == "none":
        return ("Nothing in the catalog satisfies this (or it is out of scope). A correct reply says so plainly; "
                "it may offer real alternatives from the catalog but must not present them as what was asked for.")
    parts = [f"How the expected answer was computed: {case['source']}."]
    if case["must_include"]:
        parts.append(f"Must mention: {', '.join(case['must_include'])}.")
    if case["min_acceptable"]:
        parts.append(f"Should name at least {case['min_acceptable']} of the {len(case['acceptable'])} correct products.")
    if case["forbidden"]:
        parts.append(f"Recommending any of these is wrong: {', '.join(case['forbidden'][:15])}.")
    return " ".join(parts)


def judge(case: dict, reply: str) -> dict:
    mentioned = [t for t in dict.fromkeys(_TOKEN.findall(reply)) if t in _rows and (case["numeric_models"] or not t.isdigit())]
    asked = [t for t in _TOKEN.findall(case["question"]) if t in _rows]
    models = list(dict.fromkeys([*case["must_include"], *asked, *mentioned, *case["acceptable"][:5]]))[:25]
    user = json.dumps({
        "question": case["question"],
        "expected": _expectation(case),
        "case_facts": case.get("facts", []),
        "catalog_records": [record(m) for m in models],
        "assistant_reply": reply,
    }, indent=1)
    res = _openai().chat.completions.create(
        model=settings.judge_model,
        temperature=0,
        messages=[{"role": "system", "content": RUBRIC}, {"role": "user", "content": user}],
        response_format={"type": "json_schema", "json_schema": {"name": "grade", "strict": True, "schema": SCHEMA}},
    )
    grade = json.loads(res.choices[0].message.content)
    # enforce the rule in code rather than trusting the judge to apply it
    wrong = [c for c in grade["claims"] if not c["correct"]]
    if wrong and grade["verdict"] == "pass":
        grade["verdict"] = "fail"
        grade["issues"].append("overridden: incorrect claim(s): " + "; ".join(f"{c['claim']} (catalog: {c['catalog_value']})" for c in wrong))
    return grade


def calibrate(cases: dict[str, dict]) -> list[dict]:
    """Replies with known verdicts. A judge that passes a planted error can't be trusted for this run."""
    w = cases["wrench-1"]
    j = cases["jacket-1"]
    p = cases["price-2"]
    price = record(p["must_include"][0])["msrp_usd"]
    probes = [
        ("wrong price", w, ("You have two options: GDS18V-30CPN ($199, 652 ft-lbs fastening torque) and GDS18V-800CPN "
                           "($299, 1,450 ft-lbs). Both are bare tools."), "fail"),
        ("false 'not available'", j, "Sorry, we don't carry an 18V heated jacket in women's medium.", "fail"),
        ("answered instead of asking", cases["clarify-1"],
         "You can buy it at Home Depot, Lowe's and Amazon.", "fail"),
        ("correct answer", p, f"The {p['must_include'][0]} has an MSRP of ${price:.2f}.", "pass"),
    ]
    out = []
    for name, case, reply, want in probes:
        got = judge(case, reply)["verdict"]
        out.append({"probe": name, "expected": want, "got": got, "ok": got == want})
    return out

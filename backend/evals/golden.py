"""Build the golden set: questions with expected answers computed straight from the CSV.

Deliberately independent of app/ (plain csv + json, own filters), so a bug in the agent's tools can't also be
baked into the expected answers.

  uv run python -m evals.golden        # writes evals/golden.jsonl

Case fields
  id, category, question
  expect          "answer" | "clarify" | "none" (should say it's not available / can't help)
  must_include    models that must appear in the reply
  acceptable      every correct product (for precision); must_include is a subset
  min_acceptable  at least this many of `acceptable` must appear (list questions with many matches)
  context_ok      models that are fine to mention but aren't the answer (e.g. alternative-spec matches)
  forbidden       wrong answers: mentioning any fails the case
  any_text        groups of phrases; each group needs at least one phrase in the reply
  numeric_models  count digit-only model numbers (Dremel "8984") as mentions
  source          how the expectation was computed
"""

import csv
import difflib
import json
import random
import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / "data" / "bosch_product_catalog_mock.csv"
OUT = Path(__file__).with_name("golden.jsonl")
rng = random.Random(7)  # deterministic sample: the golden set only changes when the data or this file does


def load() -> list[dict]:
    rows = list(csv.DictReader(DATA.open(encoding="utf-8")))
    for r in rows:
        r["specs"] = json.loads(r["technical_specs"] or "{}")
        r["price"] = float(r["msrp_usd"])
        r["compat"] = [t.strip() for t in r["compatible_with"].split("|") if t.strip()]
    return rows


R = load()
BY = {r["model_number"]: r for r in R}
ACTIVE = "Active"


def money(p: float) -> list[str]:
    return [f"{p:.2f}", f"{p:,.2f}"] + ([f"${int(p)}", f"${int(p):,}"] if p == int(p) else [])


def models(rows) -> list[str]:
    return [r["model_number"] for r in sorted(rows, key=lambda r: r["price"])]


def referenced(models: list[str]) -> list[str]:
    """Other catalog models named in these products' own data (box contents, compatibility, replacement)."""
    out = []
    for m in models:
        r = BY[m]
        text = " ".join([r["whats_in_the_box"], r["compatible_with"], r["replacement_model"], r["key_features"]])
        out += [t for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9-]*[A-Za-z0-9]", text) if t in BY and t != m]
    return out


def case(id, category, question, expect="answer", must=(), acceptable=(), min_acceptable=0, context_ok=(),
         forbidden=(), any_text=(), numeric_models=False, source=""):
    return {"id": id, "category": category, "question": question, "expect": expect, "must_include": list(must),
            "acceptable": list(dict.fromkeys([*must, *acceptable])), "min_acceptable": min_acceptable,
            "context_ok": list(dict.fromkeys([*context_ok, *referenced(must)])), "forbidden": list(forbidden), "any_text": [list(g) for g in any_text],
            "numeric_models": numeric_models, "source": source}


cases: list[dict] = []

# 1. Price lookups: one active product per category
for i, cat in enumerate(sorted({r["category"] for r in R})):
    r = rng.choice([x for x in R if x["category"] == cat and x["status"] == ACTIVE])
    cases.append(case(f"price-{i + 1}", "lookup", f"How much is the {r['model_number']}?", must=[r["model_number"]],
                      any_text=[money(r["price"])], numeric_models=r["model_number"].isdigit(),
                      source=f"msrp_usd={r['price']}"))

# 2. Availability
disc_rep = [r for r in R if r["status"] == "Discontinued" and r["replacement_model"]]
disc_none = [r for r in R if r["status"] == "Discontinued" and not r["replacement_model"]]
for i, r in enumerate(rng.sample(disc_rep, 4)):
    cases.append(case(f"avail-repl-{i + 1}", "availability", f"Is the {r['model_number']} still available? If not, what replaced it?",
                      must=[r["model_number"], r["replacement_model"]], any_text=[["discontinued"]],
                      source=f"Discontinued, replacement_model={r['replacement_model']}"))
for i, r in enumerate(rng.sample(disc_none, 3)):
    cases.append(case(f"avail-norepl-{i + 1}", "availability", f"Is the {r['model_number']} still available?",
                      must=[r["model_number"]],
                      any_text=[["discontinued"], ["no replacement", "no recorded replacement", "not list", "no listed replacement",
                                                    "doesn't have a replacement", "does not have a replacement",
                                                    "no direct replacement", "isn't a replacement", "not recorded"]],
                      source="Discontinued, replacement_model empty"))
for status, phrase, n in [("Temporarily Out of Stock", "out of stock", 2), ("Coming Soon", "coming soon", 2)]:
    for i, r in enumerate(rng.sample([x for x in R if x["status"] == status], n)):
        cases.append(case(f"avail-{phrase.replace(' ', '-')}-{i + 1}", "availability", f"Can I buy the {r['model_number']}?",
                          must=[r["model_number"]], any_text=[[phrase]], source=f"status={status}"))

# 3. Compare: bare tool vs kit of the same family (identical tool specs, different kit)
pairs = []
for r in R:
    if r["status"] == ACTIVE and r["model_number"].endswith("N") and r["category"] == "Power Tools":
        kit = BY.get(r["model_number"][:-1] + "B")
        if kit and kit["status"] == ACTIVE and kit["battery_included"] == "Yes":
            pairs.append((r, kit))
for i, (a, b) in enumerate(rng.sample(pairs, 3)):
    cases.append(case(f"compare-{i + 1}", "compare", f"What's the difference between the {a['model_number']} and the {b['model_number']}?",
                      must=[a["model_number"], b["model_number"]], any_text=[["batter"], money(a["price"]), money(b["price"])],
                      source="same family: bare tool (N) vs kit (B)"))

# 4. Spec searches
wrenches = [r for r in R if r["product_type"] == "Impact Wrench" and r["voltage_v"] == "18"]
for i, (t, p) in enumerate([(500, 300), (300, 200), (1000, 400)]):
    ok = [r for r in wrenches if r["status"] == ACTIVE and r["price"] <= p and r["specs"]["max_fastening_torque_ft_lbs"] >= t]
    nut = [r for r in wrenches if r["status"] == ACTIVE and r["price"] <= p and r["specs"]["nut_busting_torque_ft_lbs"] >= t and r not in ok]
    weak = [r for r in wrenches if r["specs"]["max_fastening_torque_ft_lbs"] < t and r["specs"]["nut_busting_torque_ft_lbs"] < t]
    cases.append(case(f"wrench-{i + 1}", "spec-search", f"I need an 18V impact wrench with at least {t} ft-lbs of torque under ${p}.",
                      expect="answer" if ok else "none", must=models(ok)[:3], acceptable=models(ok), context_ok=models(nut),
                      forbidden=models(weak), source=f"Impact Wrench, 18V, Active, msrp<={p}, fastening>={t}; forbidden: both torques <{t}"))

lasers = [r for r in R if r["subcategory"] == "Line Lasers"]
for i, rng_ft in enumerate([65, 130, 165]):
    green = [r for r in lasers if r["specs"].get("beam_color") == "Green" and r["status"] == ACTIVE]
    ok = [r for r in green if r["specs"].get("working_range_ft", 0) >= rng_ft]
    rx = [r for r in green if r["specs"].get("working_range_ft", 0) < rng_ft <= r["specs"].get("range_with_receiver_ft", 0)]
    short = [r for r in green if r["specs"].get("range_with_receiver_ft", r["specs"].get("working_range_ft", 0)) < rng_ft]
    red = [r for r in lasers if r["specs"].get("beam_color") == "Red" and r["status"] == ACTIVE]
    cases.append(case(f"laser-{i + 1}", "spec-search", f"Do you have a green-beam line laser with at least {rng_ft} ft range?",
                      acceptable=models(ok), min_acceptable=min(3, len(ok)), context_ok=models(rx), forbidden=models(short + red),
                      source=f"Line Lasers, Green, Active, working_range_ft>={rng_ft}; forbidden: shorter range or red beam"))

drills = [r for r in R if r["product_type"] == "Drill/Driver" and r["status"] == ACTIVE]
for i, (v, p) in enumerate([("18", 150), ("12", 130)]):
    ok = [r for r in drills if r["voltage_v"] == v and r["price"] <= p]
    other_v = [r for r in drills if r["voltage_v"] != v and r["price"] <= p]
    hammer = [r for r in R if r["product_type"] == "Hammer Drill/Driver" and r["voltage_v"] == v and r["price"] <= p]
    cases.append(case(f"drill-{i + 1}", "spec-search", f"What {v}V drill/drivers do you have under ${p}?",
                      acceptable=models(ok), min_acceptable=min(2, len(ok)), forbidden=models(other_v), context_ok=models(hammer),
                      source=f"Drill/Driver, {v}V, Active, msrp<={p}; forbidden: other voltage"))

jackets = [r for r in R if r["product_type"] == "Heated Jacket"]
size_word = {"M": "medium", "L": "large", "2XL": "2XL", "3XL": "3XL"}
for i, (v, fit, size) in enumerate([("18", "Women's", "M"), ("12", "Men's", "3XL"), ("18", "Women's", "L"), ("12", "Women's", "3XL")]):
    def match(r, f, v=v, size=size):
        return r["voltage_v"] == v and r["specs"]["fit"] == f and r["specs"]["size"] == size

    ok = [r for r in jackets if match(r, fit) and r["status"] == ACTIVE]
    other_fit = "Men's" if fit == "Women's" else "Women's"
    cases.append(case(f"jacket-{i + 1}", "spec-search", f"Do you have the {v}V heated jacket in a {fit.lower()} {size_word[size]}?",
                      expect="answer" if ok else "none", must=models(ok), acceptable=models(ok),
                      forbidden=models([r for r in jackets if match(r, other_fit)]) if ok else [],
                      source=f"Heated Jacket, {v}V, fit={fit}, size={size}, Active"))

# 5. Compatibility
blades = [r for r in R if r["product_type"] == "Oscillating Multi-Tool Blade" and r["status"] != "Discontinued"]
def fits(r, tier):  # whole-word tier name in compatible_with ("StarlockPlus" doesn't match "StarlockMax ... only")
    return any(tier in [w.strip(" ,") for w in t.split()] for t in r["compat"])


for i, (tool, tier) in enumerate([("GOP18V-1300N", "StarlockPlus"), ("GOP12V-75N", "Starlock")]):
    assert BY[tool]["specs"]["accessory_interface"] == tier
    ok = [r for r in blades if fits(r, tier)]
    cases.append(case(f"compat-{i + 1}", "compatibility", f"Which oscillating blades fit my {tool}?",
                      acceptable=models(ok), min_acceptable=2, forbidden=models([r for r in blades if r not in ok]),
                      source=f"{tool} accessory_interface={tier}; blades whose compatible_with names {tier}"))
dremel = [r for r in R if "Dremel 4300" in r["compat"] and r["status"] != "Discontinued"]
cases.append(case("compat-3", "compatibility", "Which accessories fit my Dremel 4300?", acceptable=models(dremel), min_acceptable=2,
                  numeric_models=True, source="compatible_with lists 'Dremel 4300'"))

# 6. Clarify: nothing names a product
for i, q in enumerate(["Where can I buy it?", "Is this drill still available?", "How much does that one cost?"]):
    cases.append(case(f"clarify-{i + 1}", "clarify", q, expect="clarify", source="no product in context"))

# 7. Not available / out of scope
not_found = ["couldn't find", "could not find", "not find", "no product", "not in the catalog", "isn't in", "not in our",
             "doesn't exist", "does not exist", "not found", "unable to find", "don't have", "do not have", "can't help",
             "cannot help", "not able to help", "only help", "only assist", "don't carry", "do not carry", "not available"]
cases += [
    case("none-1", "not-found", "Do you have the GSR99V-999ZZ drill?", expect="none", any_text=[not_found], source="no such model"),
    case("none-2", "not-found", "Do you sell the Milwaukee 2767-20 impact wrench?", expect="none", any_text=[not_found], source="other brand"),
    case("none-3", "not-found", "What's a good recipe for banana bread?", expect="none", any_text=[not_found], source="out of scope"),
]

# 8. Typos: last two characters swapped, must lead back to the real model
typos = [r for r in R if r["status"] == ACTIVE and len(r["model_number"]) > 8 and r["model_number"][-1] != r["model_number"][-2]
         and r["model_number"][:-2] + r["model_number"][-1] + r["model_number"][-2] not in BY]
for i, r in enumerate(rng.sample(typos, 3)):
    m = r["model_number"]
    typo = m[:-2] + m[-1] + m[-2]
    near = difflib.get_close_matches(typo.replace("-", ""), {k.replace("-", ""): k for k in BY}, n=5, cutoff=0.7)
    near = [k for k in BY if k.replace("-", "") in near]
    cases.append(case(f"typo-{i + 1}", "typo", f"What's the price of the {typo}?", must=[m], context_ok=near, source=f"typo of {m}"))

if __name__ == "__main__":
    with OUT.open("w") as f:
        for c in cases:
            f.write(json.dumps(c) + "\n")
    by_cat: dict[str, int] = {}
    for c in cases:
        by_cat[c["category"]] = by_cat.get(c["category"], 0) + 1
    print(f"wrote {len(cases)} cases to {OUT}: {by_cat}")

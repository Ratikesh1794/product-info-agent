"""Agent tools: deterministic catalog queries.

The LLM only chooses a tool and its arguments; every fact in an answer comes from these return values.
Each tool has a Pydantic args model, which doubles as the OpenAI function schema and the validator.
"""

import re
from collections.abc import Callable
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.services.catalog import Catalog, Product, Status, get_catalog

TOOL_CATEGORIES = {"Power Tools", "Rotary Tools"}  # things accessories fit *onto*


# ---------- helpers ----------

def _tokens(text: str) -> set[str]:
    # crude singularisation so "lasers"/"blades" match "laser"/"blade"
    return {t[:-1] if len(t) > 3 and t.endswith("s") else t for t in re.findall(r"[a-z0-9]+", text.lower())}


def _haystack(p: Product) -> set[str]:
    return _tokens(f"{p.product_name} {p.product_type} {p.subcategory} {p.category} {p.brand} {p.model_number} {p.product_line}")


def _mentions(token: str, term: str) -> bool:
    """Whole-word match: 'StarlockPlus' must not match 'StarlockMax ... only' or plain 'Starlock'."""
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])", token, re.IGNORECASE) is not None


def summary(p: Product) -> dict:
    return {
        "model_number": p.model_number,
        "product_name": p.product_name,
        "brand": p.brand,
        "category": p.category,
        "subcategory": p.subcategory,
        "product_type": p.product_type,
        "msrp_usd": p.msrp_usd,
        "status": p.status.value,
        "voltage_v": p.voltage_v,
        "battery_included": p.battery_included,
        "avg_rating": p.avg_rating,
        "specs": p.specs,
    }


def detail(p: Product) -> dict:
    # product_url is fake per the brief: never hand it to the model
    return p.model_dump(mode="json", exclude={"product_url", "derived_spec_keys"})


def _status_counts(ps: list[Product]) -> dict[str, int]:
    """Across ALL matches, not just the page shown, so counts like "32 fit" can say how many aren't Active."""
    out: dict[str, int] = {}
    for p in ps:
        out[p.status.value] = out.get(p.status.value, 0) + 1
    return out


def _status_note(counts: dict[str, int]) -> list[str]:
    other = {k: v for k, v in counts.items() if k != Status.ACTIVE.value}
    if not other:
        return []
    parts = ", ".join(f"{v} {k.lower()}" for k, v in other.items())
    return [f"Of {sum(counts.values())} matches, {parts}. Mention this when you give the count."]


def _not_found(cat: Catalog, model: str) -> dict:
    return {"found": False, "model": model, "did_you_mean": cat.suggest(model)}


class ToolArgs(BaseModel):
    # Unknown args must fail loudly: silently dropping e.g. {"fit": "Women's"} returned unfiltered results
    # and the model concluded "no women's jacket" (caught by evals/run.py --repeat).
    model_config = ConfigDict(extra="forbid")


# ---------- search_products ----------

class SpecFilter(ToolArgs):
    key: str = Field(description="Exact technical_specs key (discover via describe_catalog), e.g. 'max_fastening_torque_ft_lbs', 'working_range_ft', 'beam_color', 'size'.")
    op: Literal[">=", "<=", "==", "contains"]
    value: float | bool | str


class SearchArgs(ToolArgs):
    query: str | None = Field(None, description="Keywords that must all appear in name/product type/subcategory/model, e.g. 'impact wrench', 'line laser', 'heated jacket'.")
    category: str | None = None
    subcategory: str | None = None
    brand: str | None = None
    voltage_v: int | None = Field(None, description="12, 18 or 120")
    min_price: float | None = None
    max_price: float | None = None
    compatible_with: str | None = Field(None, description="System the product must fit, whole-word match on compatible_with, e.g. 'StarlockPlus', 'Dremel 4000', 'SDS-plus'.")
    spec_filters: list[SpecFilter] = []
    include_discontinued: bool = Field(False, description="Discontinued items are hidden unless true.")
    sort_by: Literal["price_asc", "price_desc", "rating"] = "price_asc"
    limit: int = Field(10, ge=1, le=25)


def _spec_ok(specs: dict, f: SpecFilter) -> bool | None:
    """True/False, or None when the product has no comparable value (reported, not silently dropped)."""
    if f.key not in specs:
        return None
    v = specs[f.key]
    if f.op == "contains":
        return str(f.value).lower() in str(v).lower()
    if f.op == "==":
        return str(v).lower() == str(f.value).lower()
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    try:
        target = float(f.value)
    except (TypeError, ValueError):
        return None
    return v >= target if f.op == ">=" else v <= target


def _base_match(p: Product, a: SearchArgs, q: set[str]) -> bool:
    eq = lambda x, y: y is None or x.lower() == y.lower()
    return (
        eq(p.category, a.category)
        and eq(p.subcategory, a.subcategory)
        and eq(p.brand, a.brand)
        and (a.voltage_v is None or p.voltage_v == a.voltage_v)
        and (a.min_price is None or p.msrp_usd >= a.min_price)
        and (a.max_price is None or p.msrp_usd <= a.max_price)
        and (not a.compatible_with or any(_mentions(t, a.compatible_with) for t in p.compatible_with))
        and q <= _haystack(p)
    )


def _resolve_taxonomy(cat: Catalog, category: str | None, subcategory: str | None) -> tuple[str | None, str | None, dict | None]:
    """Map case-insensitive names to real ones. A wrong name must come back as an error the model can fix,
    never as an empty result it would report as 'we don't have that'."""
    cats = {p.category.lower(): p.category for p in cat.products}
    subs = {p.subcategory.lower(): p.subcategory for p in cat.products}
    c, s = (category or "").lower() or None, (subcategory or "").lower() or None
    if c and c not in cats and c in subs and not s:  # subcategory passed as category
        c, s = None, c
    err = {}
    if c and c not in cats:
        err["category"] = {"unknown": category, "valid": sorted(cats.values())}
    if s and s not in subs:
        scope = {p.subcategory for p in cat.products if not c or p.category.lower() == c}
        err["subcategory"] = {"unknown": subcategory, "valid": sorted(scope)}
    if err:
        return None, None, {"error": "unknown_taxonomy", **err, "hint": "Retry with a valid name, or omit it and use query."}
    return cats.get(c) if c else None, subs.get(s) if s else None, None


# User words like "range" / "torque" map to more than one spec. Search uses the standard key and reports
# what the alternative would add, so the answer can mention it without a second round-trip.
ALTERNATIVE_SPECS = {
    "working_range_ft": "range_with_receiver_ft",
    "max_fastening_torque_ft_lbs": "nut_busting_torque_ft_lbs",
    "max_fastening_torque_in_lbs": "nut_busting_torque_in_lbs",
}


def _apply_specs(base: list[Product], filters: list[SpecFilter], include_discontinued: bool):
    matched, missing, hidden = [], {}, 0
    for p in base:
        results = [(f.key, _spec_ok(p.specs, f)) for f in filters]
        if any(ok is False for _, ok in results):
            continue
        visible = include_discontinued or p.status != Status.DISCONTINUED
        if gaps := [k for k, ok in results if ok is None]:
            if visible:
                for k in gaps:
                    by_type = missing.setdefault(k, {})
                    by_type[p.product_type] = by_type.get(p.product_type, 0) + 1
        elif visible:
            matched.append(p)
        else:
            hidden += 1
    return matched, missing, hidden


def _alternative_matches(base: list[Product], a: "SearchArgs", matched: list[Product]) -> dict:
    out, seen = {}, {p.model_number for p in matched}
    for i, f in enumerate(a.spec_filters):
        if (alt := ALTERNATIVE_SPECS.get(f.key)) and f.op in (">=", "<="):
            filters = [*a.spec_filters[:i], f.model_copy(update={"key": alt}), *a.spec_filters[i + 1:]]
            extra = sorted((p for p in _apply_specs(base, filters, a.include_discontinued)[0] if p.model_number not in seen),
                           key=lambda p: p.msrp_usd)
            if extra:
                out[alt] = {"extra_count": len(extra), "examples": [f"{p.model_number} (${p.msrp_usd:g})" for p in extra[:5]]}
    return out


def search_products(a: SearchArgs, cat: Catalog) -> dict:
    category, subcategory, err = _resolve_taxonomy(cat, a.category, a.subcategory)
    if err:
        return err
    a = a.model_copy(update={"category": category, "subcategory": subcategory})
    q = _tokens(a.query or "")
    base = [p for p in cat.products if _base_match(p, a, q)]

    known = {k for p in base for k in p.specs}
    if base and (bad := [f.key for f in a.spec_filters if f.key not in known]):
        counts: dict[str, int] = {}
        for p in base:
            for k in p.specs:
                counts[k] = counts.get(k, 0) + 1
        return {"error": "unknown_spec_key", "unknown": bad,
                "hint": "voltage_v, brand, price and category are top-level arguments, not spec filters.",
                "valid_keys_for_these_products": sorted(counts, key=counts.get, reverse=True)[:40]}

    matched, missing, hidden = _apply_specs(base, a.spec_filters, a.include_discontinued)
    key = {"price_asc": lambda p: p.msrp_usd, "price_desc": lambda p: -p.msrp_usd, "rating": lambda p: -(p.avg_rating or 0)}
    matched.sort(key=key[a.sort_by])
    out = {
        "total_matches": len(matched),
        "status_counts": _status_counts(matched),
        "notes": _status_note(_status_counts(matched)),
        "showing": min(len(matched), a.limit),
        "products": [summary(p) for p in matched[: a.limit]],
        "discontinued_hidden": hidden,
        # {spec_key: {product_type: n}}: pass every other filter but lack the spec, so "not listed", not "no"
        "missing_spec_data": missing,
    }
    if alt := _alternative_matches(base, a, matched):
        out["also_match_on_alternative_spec"] = alt
        out["notes"] += [f"{v['extra_count']} more match if {k} is used instead. Mention this in one line." for k, v in alt.items()]
    if len(matched) > a.limit:
        # the model only sees a page; facets describe ALL matches so it can't conclude "none exist" from page 1
        out["facets_across_all_matches"] = _facets(matched)
    if not matched:
        # zero results are often a wrong filter, not a missing product (e.g. compatible_with="18V" on apparel)
        out["zero_results_diagnosis"] = _diagnose_zero(a, cat)
    return out


def _matches(a: SearchArgs, cat: Catalog) -> list[Product]:
    q = _tokens(a.query or "")
    return _apply_specs([p for p in cat.products if _base_match(p, a, q)], a.spec_filters, a.include_discontinued)[0]


def _count(a: SearchArgs, cat: Catalog) -> int:
    return len(_matches(a, cat))


def _diagnose_zero(a: SearchArgs, cat: Catalog) -> dict:
    """For each single constraint: how many products match if only that one is dropped."""
    out = {}
    for f in ("query", "category", "subcategory", "brand", "voltage_v", "min_price", "max_price", "compatible_with"):
        if (v := getattr(a, f)) is not None and (n := _count(a.model_copy(update={f: None}), cat)):
            out[f"without {f}={v!r}"] = n
    for i, sf in enumerate(a.spec_filters):
        rest = a.model_copy(update={"spec_filters": a.spec_filters[:i] + a.spec_filters[i + 1:]})
        if n := _count(rest, cat):
            out[f"without spec {sf.key} {sf.op} {sf.value!r}"] = n
            if sf.op in ("==", "contains"):  # e.g. size "Medium" when the data says "M"
                values = sorted({str(p.specs[sf.key]) for p in _matches(rest, cat) if sf.key in p.specs})
                if 0 < len(values) <= 20:
                    out[f"values of {sf.key} in those products"] = values
    return out or {"note": "no single filter is responsible; the combination genuinely has no match"}


def _facets(ps: list[Product], max_values: int = 12) -> dict[str, dict]:
    values: dict[str, dict] = {}
    for p in ps:
        for k, v in p.specs.items():
            if isinstance(v, (str, bool)):
                values.setdefault(k, {}).setdefault(str(v), 0)
                values[k][str(v)] += 1
    useful = {k: v for k, v in values.items() if 1 < len(v) <= max_values}
    return dict(sorted(useful.items(), key=lambda kv: -sum(kv[1].values()))[:8])


# ---------- get_product ----------

class ModelArgs(ToolArgs):
    model_number: str = Field(description="Model number or SKU, e.g. 'GSR18V-535CN'. Case/punctuation-insensitive.")


def get_product(a: ModelArgs, cat: Catalog) -> dict:
    p = cat.get(a.model_number)
    return {"found": True, "product": detail(p)} if p else _not_found(cat, a.model_number)


# ---------- compare_products ----------

class CompareArgs(ToolArgs):
    model_numbers: list[str] = Field(min_length=2, max_length=4)


_COMPARE_FIELDS = [
    "brand", "category", "product_type", "product_line", "status", "msrp_usd", "voltage_v", "battery_platform",
    "battery_included", "motor_type", "weight_lbs", "dimensions_in", "whats_in_the_box", "key_features",
    "compatible_with", "warranty", "avg_rating", "launch_date", "replacement_model",
]


def compare_products(a: CompareArgs, cat: Catalog) -> dict:
    ps, missing = [], []
    for m in a.model_numbers:
        (ps.append(p) if (p := cat.get(m)) else missing.append(_not_found(cat, m)))
    if missing:
        return {"error": "not_found", "not_found": missing}

    rows = {f: [detail(p)[f] for p in ps] for f in _COMPARE_FIELDS}
    for k in sorted({k for p in ps for k in p.specs}):
        rows[f"specs.{k}"] = [p.specs.get(k) for p in ps]

    same, different = {}, {}
    for f, vals in rows.items():
        if all(v == vals[0] for v in vals):
            if vals[0] not in (None, [], ""):
                same[f] = vals[0]
        else:
            different[f] = {p.model_number: v for p, v in zip(ps, vals)}
    return {"products": [{"model_number": p.model_number, "product_name": p.product_name} for p in ps], "different": different, "same": same}


# ---------- check_availability (status + replacement + where to buy) ----------

def _replacement_changes(old: Product, new: Product) -> list[str]:
    fields = {"voltage_v": "voltage", "battery_platform": "battery platform", "battery_included": "battery included",
              "product_type": "product type", "subcategory": "subcategory"}
    return [f"{label}: {getattr(old, f)} -> {getattr(new, f)}" for f, label in fields.items() if getattr(old, f) != getattr(new, f)]


def check_availability(a: ModelArgs, cat: Catalog) -> dict:
    p = cat.get(a.model_number)
    if not p:
        return _not_found(cat, a.model_number)
    notes, replacement = [], None
    if p.status == Status.DISCONTINUED:
        if r := cat.replacement_for(p):
            replacement = {**summary(r), "differences_from_original": _replacement_changes(p, r)}
            if r.status != Status.ACTIVE:
                notes.append(f"The replacement is itself '{r.status.value}'.")
        else:
            notes.append("No replacement model is recorded in the catalog.")
        if p.available_at:
            notes.append("Retailers are still listed, but remaining stock of a discontinued item is not guaranteed.")
    elif p.status == Status.COMING_SOON and p.launch_date and p.launch_date < date.today().isoformat():
        notes.append(f"Listed as Coming Soon, but its launch date {p.launch_date} has passed; the catalog may be out of date.")
    elif p.status == Status.OUT_OF_STOCK:
        notes.append("Temporarily out of stock; retailers may restock.")
    return {
        "found": True,
        "model_number": p.model_number,
        "product_name": p.product_name,
        "status": p.status.value,
        "launch_date": p.launch_date,
        "discontinued_date": p.discontinued_date,
        "available_at": p.available_at,
        "replacement": replacement,
        "notes": notes,
    }


# ---------- find_compatible ----------

class CompatArgs(ToolArgs):
    model_number: str | None = Field(None, description="The user's tool, e.g. 'GOP18V-28N'. Uses its accessory interface / battery platform.")
    system: str | None = Field(None, description="A system name when no model is given: 'StarlockPlus', 'Dremel 4000', 'SDS-plus', 'Bosch 18V'.")
    query: str | None = Field(None, description="Narrow the accessory type, e.g. 'blade', 'battery'.")
    limit: int = Field(10, ge=1, le=25)


def find_compatible(a: CompatArgs, cat: Catalog) -> dict:
    if not (a.model_number or a.system):
        return {"error": "need model_number or system"}
    terms, notes, tool = [], [], None
    if a.model_number and not cat.get(a.model_number):
        # "Dremel 4300" isn't a product in the catalog, but 100+ accessories list it as a system they fit
        if any(_mentions(t, a.model_number) for p in cat.products for t in p.compatible_with):
            a = a.model_copy(update={"system": a.model_number, "model_number": None})
            notes.append(f"No product with model number '{a.system}', so it was matched as a system name in compatible_with.")
        else:
            return _not_found(cat, a.model_number)
    if a.model_number:
        tool = cat.get(a.model_number)
        terms.append(tool.model_number)
        if iface := tool.specs.get("accessory_interface"):
            terms.append(iface)
            conflicts = [t for t in tool.compatible_with if t.endswith(" blades") and t.removesuffix(" blades") != iface]
            if conflicts:
                notes.append(f"Tool spec says accessory interface '{iface}', but its compatibility list also mentions {conflicts}; using the interface spec.")
        elif tool.battery_platform:
            terms.append(tool.battery_platform)
    if a.system:
        terms.append(a.system)

    q = _tokens(a.query or "")
    hits = [
        p for p in cat.products
        if p is not tool and p.category not in TOOL_CATEGORIES and p.status != Status.DISCONTINUED
        and any(_mentions(t, term) for t in p.compatible_with for term in terms)
        and q <= _haystack(p)
    ]
    hits.sort(key=lambda p: p.msrp_usd)
    counts = _status_counts(hits)
    return {"matched_on": terms, "total_matches": len(hits), "status_counts": counts,
            "products": [summary(p) for p in hits[: a.limit]], "notes": notes + _status_note(counts)}


# ---------- describe_catalog ----------

class DescribeArgs(ToolArgs):
    category: str | None = None
    subcategory: str | None = None


def describe_catalog(a: DescribeArgs, cat: Catalog) -> dict:
    category, subcategory, err = _resolve_taxonomy(cat, a.category, a.subcategory)
    if err:
        return err
    a = DescribeArgs(category=category, subcategory=subcategory)
    ps = [p for p in cat.products if (not a.category or p.category == a.category)
          and (not a.subcategory or p.subcategory == a.subcategory)]
    if not a.category and not a.subcategory:
        cats: dict[str, dict[str, int]] = {}
        for p in ps:
            cats.setdefault(p.category, {}).setdefault(p.subcategory, 0)
            cats[p.category][p.subcategory] += 1
        return {"categories": cats, "brands": sorted({p.brand for p in ps})}
    specs: dict[str, dict] = {}
    for p in ps:
        for k, v in p.specs.items():
            s = specs.setdefault(k, {"count": 0, "examples": []})
            s["count"] += 1
            if v not in s["examples"] and len(s["examples"]) < 4:
                s["examples"].append(v)
    types: dict[str, int] = {}
    for p in ps:
        types[p.product_type] = types.get(p.product_type, 0) + 1
    return {"product_count": len(ps), "product_types": types, "spec_keys": dict(sorted(specs.items(), key=lambda kv: -kv[1]["count"]))}


# ---------- registry ----------

TOOLS: dict[str, tuple[type[BaseModel], Callable[[Any, Catalog], dict], str]] = {
    "search_products": (SearchArgs, search_products, "Find products by keywords, category, voltage, price and technical spec filters. Discontinued items hidden by default. Reports products lacking a filtered spec in missing_spec_data."),
    "get_product": (ModelArgs, get_product, "Full details of one product by model number or SKU. Returns did_you_mean suggestions if not found."),
    "compare_products": (CompareArgs, compare_products, "Compare 2-4 products; returns only the fields that differ plus the shared ones."),
    "check_availability": (ModelArgs, check_availability, "Status (Active/Discontinued/Out of Stock/Coming Soon), replacement model with how it differs, retailers, and caveats."),
    "find_compatible": (CompatArgs, find_compatible, "Accessories/batteries that fit a given tool model or system (e.g. StarlockPlus, Dremel 4000). Tier-aware whole-word matching."),
    "describe_catalog": (DescribeArgs, describe_catalog, "Categories/subcategories, or for a category: product types and spec keys with example values. Use before spec filtering."),
}


def openai_tools() -> list[dict]:
    return [
        {"type": "function", "function": {"name": n, "description": d, "parameters": m.model_json_schema()}}
        for n, (m, _, d) in TOOLS.items()
    ]


def run_tool(name: str, args_json: str, cat: Catalog | None = None) -> dict:
    """Validate + execute. Errors are returned (not raised) so the model can correct itself."""
    if name not in TOOLS:
        return {"error": f"unknown tool {name}"}
    model, fn, _ = TOOLS[name]
    try:
        args = model.model_validate_json(args_json or "{}")
    except ValidationError as e:
        return {"error": "invalid_arguments", "details": e.errors(include_url=False, include_context=False)}
    return fn(args, cat or get_catalog())

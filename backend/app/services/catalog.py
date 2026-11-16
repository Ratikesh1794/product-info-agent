"""In-memory product catalog: load, clean, normalise and index the CSV once at startup.

2.3k rows fit in RAM, so no DB. Every agent fact must come through this module.
"""

import csv
import difflib
import json
import re
from collections import Counter
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from app.core.config import settings


class Status(str, Enum):
    ACTIVE = "Active"
    DISCONTINUED = "Discontinued"
    OUT_OF_STOCK = "Temporarily Out of Stock"
    COMING_SOON = "Coming Soon"


class Product(BaseModel):
    sku: str
    model_number: str
    brand: str
    product_name: str
    category: str
    subcategory: str
    product_type: str
    product_line: str
    status: Status
    launch_date: str | None
    discontinued_date: str | None
    replacement_model: str | None
    msrp_usd: float
    short_description: str
    long_description: str
    key_features: list[str]
    whats_in_the_box: list[str]
    power_source: str | None
    voltage_v: int | None
    battery_platform: str | None
    battery_included: bool | None
    motor_type: str | None
    weight_lbs: float | None
    dimensions_in: str | None
    compatible_with: list[str]
    specs: dict
    warranty: str | None
    avg_rating: float | None
    review_count: int | None
    available_at: list[str]
    product_url: str | None  # fake per brief: never presented as a real link


# Torque appears in both in-lbs and ft-lbs keys; mirror each into the other unit so
# a single filter ("ft_lbs >= 500") works across product types.
_UNIT_MIRRORS = {"_in_lbs": ("_ft_lbs", 1 / 12), "_ft_lbs": ("_in_lbs", 12)}


def normalize_model(s: str) -> str:
    """'gsr18v 535cn' / 'GSR18V-535CN' -> 'GSR18V535CN'."""
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def _opt(v: str) -> str | None:
    return v.strip() or None


def _num(v: str, cast=float):
    return cast(float(v)) if v.strip() else None


def _split(v: str) -> list[str]:
    return [p.strip() for p in v.split("|") if p.strip()]


def _specs(raw: str) -> dict:
    specs = json.loads(raw) if raw.strip() else {}
    for key, val in list(specs.items()):
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            continue
        for suffix, (other, factor) in _UNIT_MIRRORS.items():
            if key.endswith(suffix):
                specs.setdefault(key[: -len(suffix)] + other, round(val * factor, 1))
    return specs


def _parse_row(r: dict) -> Product:
    return Product(
        sku=r["sku"],
        model_number=r["model_number"].strip(),
        brand=r["brand"],
        product_name=r["product_name"],
        category=r["category"],
        subcategory=r["subcategory"],
        product_type=r["product_type"],
        product_line=r["product_line"],
        status=Status(r["status"]),
        launch_date=_opt(r["launch_date"]),
        discontinued_date=_opt(r["discontinued_date"]),
        replacement_model=_opt(r["replacement_model"]),
        msrp_usd=float(r["msrp_usd"]),
        short_description=r["short_description"],
        long_description=r["long_description"],
        key_features=_split(r["key_features"]),
        whats_in_the_box=_split(r["whats_in_the_box"]),
        power_source=_opt(r["power_source"]),
        voltage_v=_num(r["voltage_v"], int),
        battery_platform=_opt(r["battery_platform"]),
        battery_included={"Yes": True, "No": False}.get(r["battery_included"]),
        motor_type=_opt(r["motor_type"]),
        weight_lbs=_num(r["weight_lbs"]),
        dimensions_in=_opt(r["dimensions_in"]),
        compatible_with=_split(r["compatible_with"]),
        specs=_specs(r["technical_specs"]),
        warranty=_opt(r["warranty"]),
        avg_rating=_num(r["avg_rating"]),
        review_count=_num(r["review_count"], int),
        available_at=_split(r["available_at"]),
        product_url=_opt(r["product_url"]),
    )


class Catalog:
    def __init__(self, products: list[Product]):
        self.products = products
        self._by_model = {normalize_model(p.model_number): p for p in products}
        self._by_sku = {p.sku: p for p in products}
        assert len(self._by_model) == len(products), "model_number must be unique"

    @classmethod
    def from_csv(cls, path: Path) -> "Catalog":
        with path.open(encoding="utf-8") as f:
            return cls([_parse_row(r) for r in csv.DictReader(f)])

    def get(self, model_or_sku: str) -> Product | None:
        return self._by_model.get(normalize_model(model_or_sku)) or self._by_sku.get(model_or_sku.strip())

    def suggest(self, model: str, n: int = 3) -> list[str]:
        """Closest model numbers for a typo / partial model, so the agent can ask 'did you mean'."""
        hits = difflib.get_close_matches(normalize_model(model), self._by_model, n=n, cutoff=0.75)
        return [self._by_model[h].model_number for h in hits]

    def replacement_for(self, p: Product) -> Product | None:
        return self.get(p.replacement_model) if p.replacement_model else None

    def spec_keys(self, category: str | None = None) -> dict[str, int]:
        """Spec keys (with frequency) for a category; lets the LLM discover filters among ~175 keys."""
        c = Counter(k for p in self.products if not category or p.category == category for k in p.specs)
        return dict(c.most_common())

    def audit(self) -> dict[str, list[str]]:
        """Data-quality issues the agent must not paper over."""
        return {
            "discontinued_no_replacement": [
                p.model_number for p in self.products if p.status == Status.DISCONTINUED and not p.replacement_model
            ],
            "name_model_mismatch": [
                p.model_number
                for p in self.products
                if p.brand == "Bosch"
                and re.match(r"^[A-Z0-9-]{4,}\s", p.product_name)
                and not p.product_name.startswith(p.model_number + " ")
            ],
            "empty_specs": [p.model_number for p in self.products if not p.specs],
        }


@lru_cache
def get_catalog() -> Catalog:
    return Catalog.from_csv(settings.catalog_path)

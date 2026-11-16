from pydantic import BaseModel


class RelatedProduct(BaseModel):
    model_number: str
    product_name: str
    status: str
    msrp_usd: float


class ProductDetail(BaseModel):
    """Everything the product modal shows. Specs are the catalog's own (no derived unit mirrors);
    product_url is left out because the brief says catalog URLs are fake."""

    model_number: str
    sku: str
    brand: str
    product_name: str
    category: str
    subcategory: str
    product_type: str
    product_line: str
    status: str
    launch_date: str | None
    discontinued_date: str | None
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
    replacement: RelatedProduct | None
    replaces: list[RelatedProduct]  # discontinued products that point to this one

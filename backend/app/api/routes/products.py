"""Product detail for the UI's product modal, straight from the catalog (no LLM involved)."""

from fastapi import APIRouter, HTTPException

from app.schemas.product import ProductDetail, RelatedProduct
from app.services.catalog import Product, get_catalog

router = APIRouter(prefix="/products", tags=["products"])


def _related(p: Product) -> RelatedProduct:
    return RelatedProduct(model_number=p.model_number, product_name=p.product_name, status=p.status.value, msrp_usd=p.msrp_usd)


@router.get("/{model_number}", response_model=ProductDetail)
def get_product(model_number: str) -> ProductDetail:
    cat = get_catalog()
    p = cat.get(model_number)
    if not p:
        raise HTTPException(404, {"message": "Product not found", "did_you_mean": cat.suggest(model_number)})
    data = p.model_dump(mode="json", exclude={"product_url", "derived_spec_keys", "replacement_model"})
    data["status"] = p.status.value
    data["specs"] = {k: v for k, v in p.specs.items() if k not in p.derived_spec_keys}
    data["replacement"] = _related(r) if (r := cat.replacement_for(p)) else None
    data["replaces"] = [_related(o) for o in cat.products if o.replacement_model == p.model_number]
    return ProductDetail(**data)

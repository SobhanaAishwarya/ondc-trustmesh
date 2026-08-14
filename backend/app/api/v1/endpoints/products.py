"""Product catalog: sellers manage their own inventory, everyone else can
browse/search the active catalog. `DELETE` soft-deletes (`is_active=False`)
rather than removing the row — orders reference `product_id` by foreign key,
so hard-deleting a product with order history would break that trail.
"""

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, or_, select

from app.api.deps import CurrentSeller, DbSession
from app.core.cache import cache_delete, cache_get, cache_incr, cache_set
from app.models.product import Product
from app.schemas.common import Page
from app.schemas.product import ProductCreate, ProductRead, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])

# Short TTLs deliberately: these are hot, cheap-to-recompute reads (the
# brief's "Redis caching ... hot reads (trust scores, product listings)
# are the natural first target"), not a cache meant to serve stale data
# for long. `list_products`' cache key embeds a version counter that
# every write bumps (`_LIST_VERSION_KEY`) — cheaper than tracking and
# deleting every filter-combination key a write could have affected.
PRODUCT_CACHE_TTL_SECONDS = 15
PRODUCT_LIST_CACHE_TTL_SECONDS = 15
_LIST_VERSION_KEY = "products:list:version"


def _product_cache_key(product_id: uuid.UUID) -> str:
    return f"product:{product_id}"


def _list_cache_key(category, seller_id, q, limit, offset) -> str:
    version = cache_get(_LIST_VERSION_KEY) or "0"
    return f"products:list:v{version}:{category}:{seller_id}:{q}:{limit}:{offset}"


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, seller: CurrentSeller, db: DbSession) -> ProductRead:
    product = Product(seller_id=seller.id, **payload.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    cache_incr(_LIST_VERSION_KEY)
    return ProductRead.model_validate(product)


@router.get("", response_model=Page[ProductRead])
def list_products(
    db: DbSession,
    category: str | None = None,
    seller_id: uuid.UUID | None = None,
    q: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> Page[ProductRead]:
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    cache_key = _list_cache_key(category, seller_id, q, limit, offset)
    cached = cache_get(cache_key)
    if cached is not None:
        return Page[ProductRead].model_validate_json(cached)

    conditions = [Product.is_active.is_(True)]
    if category:
        conditions.append(Product.category == category)
    if seller_id:
        conditions.append(Product.seller_id == seller_id)
    if q:
        like = f"%{q}%"
        conditions.append(or_(Product.name.ilike(like), Product.description.ilike(like)))

    total = db.scalar(select(func.count()).select_from(Product).where(*conditions)) or 0
    products = db.scalars(
        select(Product).where(*conditions).order_by(Product.created_at.desc()).limit(limit).offset(offset)
    ).all()

    result = Page(items=[ProductRead.model_validate(p) for p in products], total=total, limit=limit, offset=offset)
    cache_set(cache_key, result.model_dump_json(), PRODUCT_LIST_CACHE_TTL_SECONDS)
    return result


@router.get("/mine", response_model=list[ProductRead])
def list_my_products(seller: CurrentSeller, db: DbSession) -> list[ProductRead]:
    products = db.scalars(
        select(Product).where(Product.seller_id == seller.id).order_by(Product.created_at.desc())
    ).all()
    return [ProductRead.model_validate(p) for p in products]


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: uuid.UUID, db: DbSession) -> ProductRead:
    cache_key = _product_cache_key(product_id)
    cached = cache_get(cache_key)
    if cached is not None:
        return ProductRead.model_validate_json(cached)

    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    result = ProductRead.model_validate(product)
    cache_set(cache_key, result.model_dump_json(), PRODUCT_CACHE_TTL_SECONDS)
    return result


@router.patch("/{product_id}", response_model=ProductRead)
def update_product(product_id: uuid.UUID, payload: ProductUpdate, seller: CurrentSeller, db: DbSession) -> ProductRead:
    product = _get_owned_product(db, product_id, seller.id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)
    db.commit()
    db.refresh(product)
    cache_delete(_product_cache_key(product_id))
    cache_incr(_LIST_VERSION_KEY)
    return ProductRead.model_validate(product)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_product(product_id: uuid.UUID, seller: CurrentSeller, db: DbSession) -> None:
    product = _get_owned_product(db, product_id, seller.id)
    product.is_active = False
    db.commit()
    cache_delete(_product_cache_key(product_id))
    cache_incr(_LIST_VERSION_KEY)


def _get_owned_product(db: DbSession, product_id: uuid.UUID, seller_id: uuid.UUID) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    if product.seller_id != seller_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You do not own this product")
    return product

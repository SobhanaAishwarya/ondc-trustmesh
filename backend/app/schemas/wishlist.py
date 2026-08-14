import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.product import ProductRead


class WishlistItemCreate(BaseModel):
    product_id: uuid.UUID


class WishlistItemRead(BaseModel):
    id: uuid.UUID
    product: ProductRead
    created_at: datetime

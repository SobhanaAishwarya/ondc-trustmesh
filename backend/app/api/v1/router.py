from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    disputes,
    fraud,
    orders,
    products,
    recommendations,
    reviews,
    trust,
    wishlist,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(products.router)
api_router.include_router(orders.router)
api_router.include_router(fraud.router)
api_router.include_router(trust.router)
api_router.include_router(reviews.router)
api_router.include_router(recommendations.router)
api_router.include_router(disputes.router)
api_router.include_router(wishlist.router)
api_router.include_router(admin.router)

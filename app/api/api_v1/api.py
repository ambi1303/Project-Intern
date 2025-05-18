from fastapi import APIRouter
from app.api.api_v1.endpoints import auth, users, wallet, transactions, admin

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(wallet.router, prefix="/wallet", tags=["wallet"])
api_router.include_router(transactions.router, prefix="/transactions", tags=["transactions"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"]) 
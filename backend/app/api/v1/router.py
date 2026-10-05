from fastapi import APIRouter

from app.api.v1.endpoints import auth, behavioral, blockchain, copilot, data_status, fraud, health, investigation, security, transactions

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(transactions.router)
api_router.include_router(fraud.router)
api_router.include_router(behavioral.router)
api_router.include_router(blockchain.router)
api_router.include_router(security.router)
api_router.include_router(data_status.router)
api_router.include_router(investigation.router)
api_router.include_router(copilot.router)

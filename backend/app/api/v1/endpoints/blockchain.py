from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_current_user
from app.models.user import User
from app.services.graph_service import GraphUnavailableError, get_graph_service

router = APIRouter(prefix="/blockchain", tags=["blockchain"])


@router.get("/wallets/flagged")
def list_flagged_wallets(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Real entry point for an analyst who doesn't already have a wallet
    address to investigate: lists addresses actually flagged in the
    ingested Ethereum data (is_flagged, derived from fan-out/velocity
    patterns — see app/data/synthetic_generator.py or the real dataset's
    FLAG column), not a hardcoded example list."""
    service = get_graph_service()
    try:
        return service.list_flagged_wallets(limit=limit)
    except GraphUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))


@router.get("/wallets/{address}")
def get_wallet(address: str, current_user: User = Depends(get_current_user)):
    service = get_graph_service()
    try:
        wallet = service.get_wallet(address)
    except GraphUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return wallet


@router.get("/wallets/{address}/neighborhood")
def get_wallet_neighborhood(
    address: str,
    depth: int = Query(1, ge=1, le=3),
    current_user: User = Depends(get_current_user),
):
    service = get_graph_service()
    try:
        neighborhood = service.get_neighborhood(address, depth=depth)
    except GraphUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return neighborhood


@router.get("/status")
def blockchain_service_status(current_user: User = Depends(get_current_user)):
    service = get_graph_service()
    is_ready = service.is_ready()
    backend = type(service).__name__
    return {"ready": is_ready, "backend": backend}

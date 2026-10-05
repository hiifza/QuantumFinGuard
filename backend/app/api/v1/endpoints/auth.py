import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (
    Role,
    TokenPayloadError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.auth import RefreshRequest, TokenPair, UserLogin, UserOut, UserRegister

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("quantumfinguard.auth")


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    user = User(
        email=payload.email,
        full_name=payload.full_name,
        hashed_password=hash_password(payload.password),
        role=Role.ANALYST.value,  # elevated roles are granted by an admin, never at self-registration
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(AuditLog(actor_user_id=user.id, action="auth.register", resource_type="user", resource_id=user.id))
    db.commit()

    return user


@router.post("/login", response_model=TokenPair)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()

    # Constant-shape failure path: don't reveal whether the email exists.
    if not user or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled.")

    from datetime import datetime, timezone
    user.last_login_at = datetime.now(timezone.utc)
    db.add(AuditLog(actor_user_id=user.id, action="auth.login", resource_type="user", resource_id=user.id))
    db.commit()

    return TokenPair(
        access_token=create_access_token(user.id, Role(user.role)),
        refresh_token=create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        claims = decode_token(payload.refresh_token)
    except TokenPayloadError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")

    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type.")

    user = db.query(User).filter(User.id == claims.get("sub")).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User no longer valid.")

    return TokenPair(
        access_token=create_access_token(user.id, Role(user.role)),
        refresh_token=create_refresh_token(user.id),
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user

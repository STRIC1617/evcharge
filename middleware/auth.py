import os
import hmac
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from config.database import get_pool


# ----------------------------
# JWT / Password configuration
# ----------------------------

# IMPORTANT: Set JWT_SECRET in your deployment environment.
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Fail fast to avoid tokens breaking on restart (common on Replit)
    raise RuntimeError(
        "JWT_SECRET environment variable is required. "
        "Set it to a stable random value (>= 32 chars)."
    )

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "60"))
REFRESH_TOKEN_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", "30"))

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

bearer_scheme = HTTPBearer(auto_error=False)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def _now_utc() -> datetime:
    return datetime.utcnow()


def generate_access_token(user: Dict[str, Any]) -> str:
    payload = {
        "sub": str(user["id"]),
        "email": user.get("email"),
        "role": user.get("role", "driver"),
        "iat": int(_now_utc().timestamp()),
        "exp": int((_now_utc() + timedelta(minutes=ACCESS_TOKEN_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _hash_refresh_token(token: str) -> str:
    # Store only a hash of refresh token in DB.
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def issue_refresh_token(user_id: int) -> str:
    raw = secrets.token_urlsafe(48)
    token_hash = _hash_refresh_token(raw)
    expires_at = _now_utc() + timedelta(days=REFRESH_TOKEN_DAYS)

    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO refresh_tokens (user_id, token_hash, expires_at)
            VALUES ($1, $2, $3)
            """,
            user_id,
            token_hash,
            expires_at,
        )
    return raw


async def rotate_refresh_token(user_id: int, refresh_token: str) -> str:
    """Revoke old refresh token and issue a new one."""
    pool = await get_pool()
    token_hash = _hash_refresh_token(refresh_token)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, expires_at, revoked_at
            FROM refresh_tokens
            WHERE user_id = $1 AND token_hash = $2
            """,
            user_id,
            token_hash,
        )
        if not row:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        if row["revoked_at"] is not None:
            raise HTTPException(status_code=401, detail="Refresh token revoked")
        if row["expires_at"] < _now_utc():
            raise HTTPException(status_code=401, detail="Refresh token expired")

        # Revoke old
        await conn.execute(
            "UPDATE refresh_tokens SET revoked_at = NOW() WHERE id = $1",
            row["id"],
        )

    return await issue_refresh_token(user_id)


async def revoke_refresh_token(user_id: int, refresh_token: str) -> None:
    pool = await get_pool()
    token_hash = _hash_refresh_token(refresh_token)
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE refresh_tokens
            SET revoked_at = NOW()
            WHERE user_id = $1 AND token_hash = $2 AND revoked_at IS NULL
            """,
            user_id,
            token_hash,
        )


def _decode_access_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as e:
        raise HTTPException(status_code=401, detail="Invalid token") from e


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> Dict[str, Any]:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing authorization token")

    payload = _decode_access_token(creds.credentials)
    user_id = int(payload.get("sub"))

    pool = await get_pool()
    async with pool.acquire() as conn:
        user_row = await conn.fetchrow(
            "SELECT id, email, name, phone, role, created_at FROM users WHERE id = $1",
            user_id,
        )
        if not user_row:
            raise HTTPException(status_code=401, detail="User not found")
        return dict(user_row)


def require_role(*roles: str):
    """FastAPI dependency to restrict endpoint to given roles."""

    async def _dep(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        if current_user.get("role") not in roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return current_user

    return _dep


def constant_time_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

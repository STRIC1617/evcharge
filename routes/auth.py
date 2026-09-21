from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional

from config.database import get_pool, ensure_wallet, get_role_summary

import os
# from dotenv import load_dotenv

# load_dotenv() # Load environment variables from .env file
# print("JWT_SECRET length:", len(os.getenv("JWT_SECRET", "")))

import secrets
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from middleware.auth import (
    get_password_hash,
    verify_password,
    generate_access_token,
    issue_refresh_token,
    rotate_refresh_token,
    revoke_refresh_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None
    phone: Optional[str] = None

class GoogleLoginRequest(BaseModel):
    credential: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


@router.post("/register")
async def register(request: RegisterRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM users WHERE email = $1", request.email)
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        password_hash = get_password_hash(request.password)
        row = await conn.fetchrow(
            """
            INSERT INTO users (email, password_hash, name, phone, auth_provider)
            VALUES ($1, $2, $3, $4, 'email')
            RETURNING id, email, name, phone, role, auth_provider, created_at
            """,
            request.email,
            password_hash,
            request.name,
            request.phone,
            
        )

        user = dict(row)
        await ensure_wallet(conn, user["id"])
        user.update(await get_role_summary(conn, user["id"], user.get("role", "driver")))

    access_token = generate_access_token(user)
    refresh_token = await issue_refresh_token(user["id"])
    return {"user": user, "token": access_token, "refresh_token": refresh_token}


@router.post("/google")
async def google_login(request: GoogleLoginRequest):
    google_client_id = os.getenv("GOOGLE_CLIENT_ID")

    if not google_client_id:
        raise HTTPException(
            status_code=500,
            detail="GOOGLE_CLIENT_ID is not configured",
        )

    try:
        google_user = id_token.verify_oauth2_token(
            request.credential,
            google_requests.Request(),
            google_client_id,
        )
    except Exception as e:
        raise HTTPException(status_code=401, detail="Invalid Google token") from e

    email = google_user.get("email")
    email_verified = google_user.get("email_verified")
    name = google_user.get("name") or email
    google_sub = google_user.get("sub")

    if not email or not email_verified or not google_sub:
        raise HTTPException(
            status_code=401,
            detail="Google account email is not verified",
        )

    pool = await get_pool()

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT *
            FROM users
            WHERE email = $1
            """,
            email,
        )

        if row:
            user = dict(row)

            updated = await conn.fetchrow(
                """
                UPDATE users
                SET
                    name = COALESCE(name, $1),
                    auth_provider = CASE
                        WHEN auth_provider = 'email' THEN 'google'
                        ELSE auth_provider
                    END,
                    google_sub = COALESCE(google_sub, $2),
                    updated_at = NOW()
                WHERE id = $3
                RETURNING id, email, name, phone, role, auth_provider, google_sub, created_at
                """,
                name,
                google_sub,
                user["id"],
            )

            safe_user = dict(updated)
        else:
            random_password = secrets.token_urlsafe(32)
            password_hash = get_password_hash(random_password)

            created = await conn.fetchrow(
                """
                INSERT INTO users (
                    email,
                    password_hash,
                    name,
                    auth_provider,
                    google_sub
                )
                VALUES ($1, $2, $3, 'google', $4)
                RETURNING id, email, name, phone, role, auth_provider, google_sub, created_at
                """,
                email,
                password_hash,
                name,
                google_sub,
            )

            safe_user = dict(created)
            await ensure_wallet(conn, safe_user["id"])

        safe_user.update(await get_role_summary(conn, safe_user["id"], safe_user.get("role", "driver")))

    access_token = generate_access_token(safe_user)
    refresh_token = await issue_refresh_token(safe_user["id"])

    return {
        "user": safe_user,
        "token": access_token,
        "refresh_token": refresh_token,
    }

@router.post("/login")
async def login(request: LoginRequest):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", request.email)
        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user = dict(row)
        if not verify_password(request.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        safe_user = {
            "id": user["id"],
            "email": user["email"],
            "name": user.get("name"),
            "phone": user.get("phone"),
            "role": user.get("role", "driver"),
            "created_at": user.get("created_at"),
        }
        safe_user.update(await get_role_summary(conn, user["id"], safe_user["role"]))

    access_token = generate_access_token(safe_user)
    refresh_token = await issue_refresh_token(safe_user["id"])
    return {"user": safe_user, "token": access_token, "refresh_token": refresh_token}


@router.post("/refresh")
async def refresh_tokens(request: RefreshRequest, current_user: dict = Depends(get_current_user)):
    # Rotates refresh token (revokes the provided token and issues a new one)
    new_refresh = await rotate_refresh_token(current_user["id"], request.refresh_token)
    new_access = generate_access_token(current_user)
    return {"token": new_access, "refresh_token": new_refresh}


@router.post("/logout")
async def logout(request: LogoutRequest, current_user: dict = Depends(get_current_user)):
    await revoke_refresh_token(current_user["id"], request.refresh_token)
    return {"message": "Logged out"}


@router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        role_summary = await get_role_summary(conn, current_user["id"], current_user.get("role", "driver"))
    return {**current_user, **role_summary}

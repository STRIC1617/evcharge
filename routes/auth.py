from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional

from config.database import get_pool

import os
from dotenv import load_dotenv

load_dotenv() # Load environment variables from .env file
print("JWT_SECRET length:", len(os.getenv("JWT_SECRET", "")))
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
            INSERT INTO users (email, password_hash, name, phone)
            VALUES ($1, $2, $3, $4)
            RETURNING id, email, name, phone, role, created_at
            """,
            request.email,
            password_hash,
            request.name,
            request.phone,
        )

        user = dict(row)

    access_token = generate_access_token(user)
    refresh_token = await issue_refresh_token(user["id"])
    return {"user": user, "token": access_token, "refresh_token": refresh_token}


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
    return current_user



@router.post("/vehicles")
async def add_vehicle(request: VehicleRequest, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            '''INSERT INTO vehicles (user_id, make, model, year, battery_capacity_kwh, license_plate)
               VALUES ($1, $2, $3, $4, $5, $6) RETURNING *''',
            current_user["id"], request.make, request.model, request.year,
            request.battery_capacity_kwh, request.connector_type, request.license_plate
        )
        return dict(row)

@router.get("/vehicles")
async def get_vehicles(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch('SELECT * FROM vehicles WHERE user_id = $1', current_user["id"])
        return [dict(row) for row in rows]

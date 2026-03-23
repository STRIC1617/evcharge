from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from config.database import get_pool
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/users", tags=["users"])


class ProfileUpdateRequest(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None


class VehicleCreateRequest(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    battery_capacity_kwh: Optional[float] = None
    connector_type: Optional[str] = None
    license_plate: Optional[str] = None
    is_default: Optional[bool] = False


class VehicleUpdateRequest(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    battery_capacity_kwh: Optional[float] = None
    connector_type: Optional[str] = None
    license_plate: Optional[str] = None
    is_default: Optional[bool] = None


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.patch("/profile")
async def update_profile(req: ProfileUpdateRequest, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE users
            SET name = COALESCE($1, name), phone = COALESCE($2, phone), updated_at = NOW()
            WHERE id = $3
            RETURNING id, email, name, phone, role, created_at, updated_at
            """,
            req.name,
            req.phone,
            current_user["id"],
        )
        return dict(row)


async def _set_default_vehicle(conn, user_id: int, vehicle_id: int):
    # Ensure only one default per user
    await conn.execute("UPDATE vehicles SET is_default = false, updated_at = NOW() WHERE user_id = $1", user_id)
    await conn.execute(
        "UPDATE vehicles SET is_default = true, updated_at = NOW() WHERE id = $1 AND user_id = $2",
        vehicle_id,
        user_id,
    )


@router.post("/vehicles")
async def add_vehicle(req: VehicleCreateRequest, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Insert
        row = await conn.fetchrow(
            """
            INSERT INTO vehicles (user_id, make, model, year, battery_capacity_kwh, connector_type, license_plate, is_default)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING *
            """,
            current_user["id"],
            req.make,
            req.model,
            req.year,
            req.battery_capacity_kwh,
            req.connector_type,
            req.license_plate,
            bool(req.is_default),
        )
        vehicle = dict(row)

        if req.is_default:
            await _set_default_vehicle(conn, current_user["id"], vehicle["id"])
            # re-fetch to return updated state
            vehicle = dict(await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1", vehicle["id"]))

        return vehicle


@router.get("/vehicles")
async def list_vehicles(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM vehicles WHERE user_id = $1 ORDER BY is_default DESC, created_at DESC",
            current_user["id"],
        )
        return [dict(r) for r in rows]


@router.patch("/vehicles/{vehicle_id}")
async def update_vehicle(vehicle_id: int, req: VehicleUpdateRequest, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT * FROM vehicles WHERE id = $1 AND user_id = $2",
            vehicle_id,
            current_user["id"],
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        row = await conn.fetchrow(
            """
            UPDATE vehicles SET
              make = COALESCE($1, make),
              model = COALESCE($2, model),
              year = COALESCE($3, year),
              battery_capacity_kwh = COALESCE($4, battery_capacity_kwh),
              connector_type = COALESCE($5, connector_type),
              license_plate = COALESCE($6, license_plate),
              updated_at = NOW()
            WHERE id = $7 AND user_id = $8
            RETURNING *
            """,
            req.make,
            req.model,
            req.year,
            req.battery_capacity_kwh,
            req.connector_type,
            req.license_plate,
            vehicle_id,
            current_user["id"],
        )

        if req.is_default is True:
            await _set_default_vehicle(conn, current_user["id"], vehicle_id)
            row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1", vehicle_id)

        return dict(row)


@router.post("/vehicles/{vehicle_id}/set-default")
async def set_default_vehicle(vehicle_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow(
            "SELECT id FROM vehicles WHERE id = $1 AND user_id = $2",
            vehicle_id,
            current_user["id"],
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        await _set_default_vehicle(conn, current_user["id"], vehicle_id)
        row = await conn.fetchrow("SELECT * FROM vehicles WHERE id = $1", vehicle_id)
        return dict(row)


@router.delete("/vehicles/{vehicle_id}")
async def delete_vehicle(vehicle_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "DELETE FROM vehicles WHERE id = $1 AND user_id = $2 RETURNING id, is_default",
            vehicle_id,
            current_user["id"],
        )
        if not row:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        # If deleted default, try to set latest as default
        if row["is_default"]:
            next_vehicle = await conn.fetchrow(
                "SELECT id FROM vehicles WHERE user_id = $1 ORDER BY created_at DESC LIMIT 1",
                current_user["id"],
            )
            if next_vehicle:
                await _set_default_vehicle(conn, current_user["id"], next_vehicle["id"])

        return {"message": "Vehicle deleted"}

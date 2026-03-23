from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import json

from config.database import get_pool
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


class BookingRequest(BaseModel):
    vehicle_id: Optional[int] = None
    station_id: int
    connector_id: int
    start_time: datetime
    end_time: datetime


def _validate_times(start_time: datetime, end_time: datetime):
    if end_time <= start_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")
    # simple sanity: max 24 hours booking window
    if (end_time - start_time) > timedelta(hours=24):
        raise HTTPException(status_code=400, detail="Booking window too long")


@router.post("")
async def create_booking(request: BookingRequest, current_user: dict = Depends(get_current_user)):
    _validate_times(request.start_time, request.end_time)

    pool = await get_pool()
    async with pool.acquire() as conn:
        # Validate connector and station mapping
        connector_row = await conn.fetchrow(
            "SELECT * FROM connectors WHERE id = $1",
            request.connector_id,
        )
        if not connector_row:
            raise HTTPException(status_code=404, detail="Connector not found")
        connector = dict(connector_row)

        if connector["station_id"] != request.station_id:
            raise HTTPException(status_code=400, detail="Connector does not belong to station")

        # Block if connector is offline/maintenance (allow future bookings even if in_use)
        if connector["status"] in ("offline", "maintenance"):
            raise HTTPException(status_code=400, detail=f"Connector is {connector['status']}")

        # Booking conflicts: other bookings
        conflict_booking = await conn.fetchrow(
            """
            SELECT id FROM bookings
            WHERE connector_id = $1
              AND status IN ('pending', 'confirmed', 'in_progress')
              AND NOT (end_time <= $2 OR start_time >= $3)
            LIMIT 1
            """,
            request.connector_id,
            request.start_time,
            request.end_time,
        )
        if conflict_booking:
            raise HTTPException(status_code=400, detail="Time slot already booked")

        # Also block if there is an active session overlapping requested window
        conflict_session = await conn.fetchrow(
            """
            SELECT id FROM sessions
            WHERE connector_id = $1
              AND status = 'active'
              AND (
                start_time <= $3
                AND (end_time IS NULL OR end_time >= $2)
              )
            LIMIT 1
            """,
            request.connector_id,
            request.start_time,
            request.end_time,
        )
        if conflict_session:
            raise HTTPException(status_code=400, detail="Connector has an active session")

        pricing_snapshot = {
            "price_per_kwh": float(connector["price_per_kwh"] or 0),
            "price_per_minute": float(connector["price_per_minute"] or 0),
            "max_power_kw": float(connector["max_power_kw"] or 0),
            "captured_at": datetime.utcnow().isoformat(),
        }

        row = await conn.fetchrow(
            """
            INSERT INTO bookings (user_id, vehicle_id, station_id, connector_id, start_time, end_time, pricing_snapshot, status, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 'confirmed', NOW())
            RETURNING *
            """,
            current_user["id"],
            request.vehicle_id,
            request.station_id,
            request.connector_id,
            request.start_time,
            request.end_time,
            json.dumps(pricing_snapshot),
        )
        return dict(row)


@router.get("")
async def list_my_bookings(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT b.*, s.name as station_name, s.address as station_address,
                   c.name as connector_name, c.connector_type, c.power_type, c.max_power_kw
            FROM bookings b
            JOIN stations s ON s.id = b.station_id
            JOIN connectors c ON c.id = b.connector_id
            WHERE b.user_id = $1
            ORDER BY b.start_time DESC
            """,
            current_user["id"],
        )
        return [dict(r) for r in rows]


@router.get("/{booking_id}")
async def get_booking(booking_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT b.*, s.name as station_name, s.address as station_address,
                   c.name as connector_name, c.connector_type, c.power_type, c.max_power_kw
            FROM bookings b
            JOIN stations s ON s.id = b.station_id
            JOIN connectors c ON c.id = b.connector_id
            WHERE b.id = $1 AND b.user_id = $2
            """,
            booking_id,
            current_user["id"],
        )
        if not row:
            raise HTTPException(status_code=404, detail="Booking not found")
        return dict(row)


@router.patch("/{booking_id}/cancel")
async def cancel_booking(booking_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE bookings
            SET status = 'cancelled', updated_at = NOW()
            WHERE id = $1 AND user_id = $2 AND status IN ('pending', 'confirmed')
            RETURNING *
            """,
            booking_id,
            current_user["id"],
        )
        if not row:
            raise HTTPException(status_code=404, detail="Booking not found or cannot be cancelled")
        return dict(row)

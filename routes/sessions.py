from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta
import json
import os

from config.database import get_pool
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

TAX_RATE = float(os.getenv("TAX_RATE", "0.10"))
BOOKING_GRACE_MIN = int(os.getenv("BOOKING_GRACE_MIN", "15"))
MAX_CLIENT_ENERGY_KWH = float(os.getenv("MAX_CLIENT_ENERGY_KWH", "200.0"))


class StartSessionRequest(BaseModel):
    booking_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    station_id: Optional[int] = None  # ignored; resolved from connector
    connector_id: int


class StopSessionRequest(BaseModel):
    energy_kwh: float


async def _lock_connector(conn, connector_id: int):
    # Atomic lock: only succeed if available
    row = await conn.fetchrow(
        """
        UPDATE connectors
        SET status = 'in_use', updated_at = NOW()
        WHERE id = $1 AND status = 'available'
        RETURNING *
        """,
        connector_id,
    )
    return dict(row) if row else None


@router.post("/start")
async def start_session(
    request: StartSessionRequest,
    current_user: dict = Depends(get_current_user),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Idempotency: if client retries start, return existing active session
        if idempotency_key:
            existing = await conn.fetchrow(
                """
                SELECT * FROM sessions
                WHERE user_id = $1 AND status = 'active' AND tariff_snapshot->>'idempotency_key' = $2
                ORDER BY start_time DESC
                LIMIT 1
                """,
                current_user["id"],
                idempotency_key,
            )
            if existing:
                return dict(existing)

        # If booking_id provided, validate it belongs to user and is usable
        booking = None
        if request.booking_id:
            booking_row = await conn.fetchrow(
                """
                SELECT * FROM bookings
                WHERE id = $1 AND user_id = $2
                """,
                request.booking_id,
                current_user["id"],
            )
            if not booking_row:
                raise HTTPException(status_code=404, detail="Booking not found")
            booking = dict(booking_row)
            if booking["status"] not in ("confirmed", "pending"):
                raise HTTPException(status_code=400, detail="Booking is not active")
            if booking["connector_id"] != request.connector_id:
                raise HTTPException(status_code=400, detail="Booking connector mismatch")

            # booking time window validation with grace
            now = datetime.utcnow()
            start_ok = booking["start_time"] - timedelta(minutes=BOOKING_GRACE_MIN)
            end_ok = booking["end_time"] + timedelta(minutes=BOOKING_GRACE_MIN)
            if not (start_ok <= now <= end_ok):
                raise HTTPException(status_code=400, detail="Booking time window not valid")

        # Lock connector atomically
        locked_connector = await _lock_connector(conn, request.connector_id)
        if not locked_connector:
            # Connector was not available (someone else took it)
            raise HTTPException(status_code=409, detail="Connector not available")

        # Derive station_id from connector to avoid mismatches
        station_id = locked_connector["station_id"]

        tariff_snapshot = {
            "price_per_kwh": float(locked_connector["price_per_kwh"] or 0),
            "price_per_minute": float(locked_connector["price_per_minute"] or 0),
            "max_power_kw": float(locked_connector["max_power_kw"] or 0),
            "captured_at": datetime.utcnow().isoformat(),
        }
        if idempotency_key:
            tariff_snapshot["idempotency_key"] = idempotency_key

        # Create session
        row = await conn.fetchrow(
            """
            INSERT INTO sessions (user_id, vehicle_id, station_id, connector_id, booking_id, start_time, tariff_snapshot, status, updated_at)
            VALUES ($1, $2, $3, $4, $5, NOW(), $6, 'active', NOW())
            RETURNING *
            """,
            current_user["id"],
            request.vehicle_id,
            station_id,
            request.connector_id,
            request.booking_id,
            json.dumps(tariff_snapshot),
        )

        # Update booking status if present
        if request.booking_id:
            await conn.execute(
                "UPDATE bookings SET status = 'in_progress', updated_at = NOW() WHERE id = $1",
                request.booking_id,
            )

        return dict(row)


@router.post("/{session_id}/stop")
async def stop_session(session_id: int, request: StopSessionRequest, current_user: dict = Depends(get_current_user)):
    if request.energy_kwh < 0 or request.energy_kwh > MAX_CLIENT_ENERGY_KWH:
        raise HTTPException(status_code=400, detail="Invalid energy_kwh")

    pool = await get_pool()
    async with pool.acquire() as conn:
        session_row = await conn.fetchrow(
            "SELECT * FROM sessions WHERE id = $1 AND user_id = $2",
            session_id,
            current_user["id"],
        )
        if not session_row:
            raise HTTPException(status_code=404, detail="Session not found")

        session = dict(session_row)
        if session["status"] != "active":
            raise HTTPException(status_code=400, detail="Session is not active")

        tariff = session["tariff_snapshot"]
        if isinstance(tariff, str):
            tariff = json.loads(tariff)

        duration_minutes = (datetime.utcnow() - session["start_time"]).total_seconds() / 60
        energy_cost = request.energy_kwh * float(tariff.get("price_per_kwh", 0) or 0)
        time_cost = duration_minutes * float(tariff.get("price_per_minute", 0) or 0)
        amount = float(energy_cost + time_cost)
        tax_amount = float(amount * TAX_RATE)
        total_amount = float(amount + tax_amount)

        result_row = await conn.fetchrow(
            """
            UPDATE sessions
            SET end_time = NOW(), energy_kwh = $1, cost = $2, status = 'completed', updated_at = NOW()
            WHERE id = $3
            RETURNING *
            """,
            request.energy_kwh,
            amount,
            session_id,
        )

        # Free connector back to available
        await conn.execute(
            "UPDATE connectors SET status = 'available', updated_at = NOW() WHERE id = $1",
            session["connector_id"],
        )

        # Update booking if exists
        if session.get("booking_id"):
            await conn.execute(
                "UPDATE bookings SET status = 'completed', updated_at = NOW() WHERE id = $1",
                session["booking_id"],
            )

        # Create invoice (still synchronous MVP)
        invoice_row = await conn.fetchrow(
            """
            INSERT INTO invoices (user_id, session_id, amount, tax_amount, total_amount, status, due_date, updated_at)
            VALUES ($1, $2, $3, $4, $5, 'pending', NOW() + INTERVAL '30 days', NOW())
            RETURNING *
            """,
            current_user["id"],
            session_id,
            amount,
            tax_amount,
            total_amount,
        )

        return {"session": dict(result_row), "invoice": dict(invoice_row)}


@router.get("")
async def list_my_sessions(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ss.*, s.name as station_name, s.address as station_address,
                   c.name as connector_name, c.connector_type, c.power_type, c.max_power_kw
            FROM sessions ss
            JOIN stations s ON s.id = ss.station_id
            JOIN connectors c ON c.id = ss.connector_id
            WHERE ss.user_id = $1
            ORDER BY ss.start_time DESC
            """,
            current_user["id"],
        )
        return [dict(r) for r in rows]


@router.get("/active")
async def list_active_sessions(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT ss.*, s.name as station_name, s.address as station_address,
                   c.name as connector_name, c.connector_type, c.power_type, c.max_power_kw
            FROM sessions ss
            JOIN stations s ON s.id = ss.station_id
            JOIN connectors c ON c.id = ss.connector_id
            WHERE ss.user_id = $1 AND ss.status = 'active'
            ORDER BY ss.start_time DESC
            """,
            current_user["id"],
        )
        return [dict(r) for r in rows]

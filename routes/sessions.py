
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
    charging_gun_id: Optional[int] = None


class StopSessionRequest(BaseModel):
    energy_kwh: float


async def _lock_connector(conn, connector_id: int):
    """
    Atomic connector lock.
    Only succeeds if connector is currently available.
    """
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


async def _lock_charging_gun(conn, charging_gun_id: int, connector_id: int):
    """Atomic gun lock. Only succeeds if the gun belongs to the connector and is available."""
    row = await conn.fetchrow(
        """
        UPDATE charging_guns
        SET status = 'in_use', last_used_at = NOW(), updated_at = NOW()
        WHERE id = $1 AND connector_id = $2 AND status = 'available'
        RETURNING *
        """,
        charging_gun_id,
        connector_id,
    )
    return dict(row) if row else None


async def _sync_connector_status(conn, connector_id: int):
    """Reflect per-gun availability onto the parent connector for connectors that use guns."""
    gun_count = await conn.fetchval(
        "SELECT COUNT(*) FROM charging_guns WHERE connector_id = $1", connector_id
    )
    if not gun_count:
        return
    available_count = await conn.fetchval(
        "SELECT COUNT(*) FROM charging_guns WHERE connector_id = $1 AND status = 'available'",
        connector_id,
    )
    await conn.execute(
        """
        UPDATE connectors
        SET status = $1, updated_at = NOW()
        WHERE id = $2 AND status NOT IN ('offline', 'maintenance')
        """,
        "available" if available_count > 0 else "in_use",
        connector_id,
    )


async def _resolve_user_vehicle(
    conn,
    user_id: int,
    requested_vehicle_id: Optional[int] = None,
) -> int:
    """
    Require user to have a registered vehicle before starting a session.
    If vehicle_id is provided, validate ownership.
    If not provided, use default/latest registered vehicle.
    """

    if requested_vehicle_id:
        vehicle = await conn.fetchrow(
            """
            SELECT id
            FROM vehicles
            WHERE id = $1 AND user_id = $2
            """,
            requested_vehicle_id,
            user_id,
        )

        if not vehicle:
            raise HTTPException(
                status_code=400,
                detail="Selected vehicle not found for this user",
            )

        return vehicle["id"]

    vehicle = await conn.fetchrow(
        """
        SELECT id
        FROM vehicles
        WHERE user_id = $1
        ORDER BY is_default DESC, created_at DESC
        LIMIT 1
        """,
        user_id,
    )

    if not vehicle:
        raise HTTPException(
            status_code=400,
            detail="Please register a vehicle before starting a charging session",
        )

    return vehicle["id"]


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
                SELECT *
                FROM sessions
                WHERE user_id = $1
                  AND status = 'active'
                  AND tariff_snapshot->>'idempotency_key' = $2
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
                SELECT *
                FROM bookings
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
                raise HTTPException(
                    status_code=400,
                    detail="Booking connector mismatch",
                )

            # Booking time window validation with grace.
            # Use DB timestamp because bookings are stored as naive TIMESTAMP.
            now = await conn.fetchval("SELECT NOW()::timestamp")

            start_ok = booking["start_time"] - timedelta(minutes=BOOKING_GRACE_MIN)
            end_ok = booking["end_time"] + timedelta(minutes=BOOKING_GRACE_MIN)

            if not (start_ok <= now <= end_ok):
                raise HTTPException(
                    status_code=400,
                    detail="Booking time window not valid",
                )

        # Require vehicle before locking connector
        vehicle_id = request.vehicle_id

        if booking and booking.get("vehicle_id"):
            vehicle_id = booking["vehicle_id"]

        vehicle_id = await _resolve_user_vehicle(
            conn,
            current_user["id"],
            vehicle_id,
        )

        # Resolve which charging gun (if any) this session should lock.
        charging_gun_id = request.charging_gun_id
        if booking and booking.get("charging_gun_id"):
            if request.charging_gun_id and request.charging_gun_id != booking["charging_gun_id"]:
                raise HTTPException(
                    status_code=400,
                    detail="charging_gun_id does not match the gun reserved on this booking",
                )
            charging_gun_id = booking["charging_gun_id"]

        connector_row = await conn.fetchrow(
            "SELECT * FROM connectors WHERE id = $1", request.connector_id
        )
        if not connector_row:
            raise HTTPException(status_code=404, detail="Connector not found")
        if connector_row["status"] in ("offline", "maintenance"):
            raise HTTPException(
                status_code=400, detail=f"Connector is {connector_row['status']}"
            )

        # If this connector has individual guns, the caller must select exactly one of them.
        connector_gun_count = await conn.fetchval(
            "SELECT COUNT(*) FROM charging_guns WHERE connector_id = $1", request.connector_id
        )
        if connector_gun_count and not charging_gun_id:
            raise HTTPException(
                status_code=400,
                detail="This connector has multiple charging guns; specify charging_gun_id",
            )

        if charging_gun_id:
            gun_row = await conn.fetchrow(
                "SELECT * FROM charging_guns WHERE id = $1", charging_gun_id
            )
            if not gun_row or gun_row["connector_id"] != request.connector_id:
                raise HTTPException(
                    status_code=404, detail="Charging gun not found for this connector"
                )

            locked_gun = await _lock_charging_gun(conn, charging_gun_id, request.connector_id)
            if not locked_gun:
                raise HTTPException(status_code=409, detail="Charging gun not available")

            await _sync_connector_status(conn, request.connector_id)
            locked_connector = dict(connector_row)
        else:
            # Lock connector atomically
            locked_connector = await _lock_connector(conn, request.connector_id)

            if not locked_connector:
                raise HTTPException(
                    status_code=409,
                    detail="Connector not available",
                )

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
            INSERT INTO sessions (
                user_id,
                vehicle_id,
                station_id,
                connector_id,
                charging_gun_id,
                booking_id,
                start_time,
                tariff_snapshot,
                status,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7, 'active', NOW())
            RETURNING *
            """,
            current_user["id"],
            vehicle_id,
            station_id,
            request.connector_id,
            charging_gun_id,
            request.booking_id,
            json.dumps(tariff_snapshot),
        )

        # Update booking status if present
        if request.booking_id:
            await conn.execute(
                """
                UPDATE bookings
                SET status = 'in_progress', updated_at = NOW()
                WHERE id = $1
                """,
                request.booking_id,
            )

        return dict(row)


@router.post("/{session_id}/stop")
async def stop_session(
    session_id: int,
    request: StopSessionRequest,
    current_user: dict = Depends(get_current_user),
):
    if request.energy_kwh < 0 or request.energy_kwh > MAX_CLIENT_ENERGY_KWH:
        raise HTTPException(status_code=400, detail="Invalid energy_kwh")

    pool = await get_pool()

    async with pool.acquire() as conn:
        session_row = await conn.fetchrow(
            """
            SELECT *
            FROM sessions
            WHERE id = $1 AND user_id = $2
            """,
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

        # Use DB/server timestamp to avoid UTC/local naive mismatch.
        now = await conn.fetchval("SELECT NOW()::timestamp")
        duration_minutes = (now - session["start_time"]).total_seconds() / 60

        energy_cost = request.energy_kwh * float(tariff.get("price_per_kwh", 0) or 0)
        time_cost = duration_minutes * float(tariff.get("price_per_minute", 0) or 0)

        amount = float(energy_cost + time_cost)
        tax_amount = float(amount * TAX_RATE)
        total_amount = float(amount + tax_amount)

        result_row = await conn.fetchrow(
            """
            UPDATE sessions
            SET
                end_time = NOW(),
                energy_kwh = $1,
                cost = $2,
                status = 'completed',
                updated_at = NOW()
            WHERE id = $3
            RETURNING *
            """,
            request.energy_kwh,
            amount,
            session_id,
        )

        # Free the specific gun (if one was locked) or the whole connector back to available
        if session.get("charging_gun_id"):
            await conn.execute(
                """
                UPDATE charging_guns
                SET status = 'available', updated_at = NOW()
                WHERE id = $1
                """,
                session["charging_gun_id"],
            )
            await _sync_connector_status(conn, session["connector_id"])
        else:
            await conn.execute(
                """
                UPDATE connectors
                SET status = 'available', updated_at = NOW()
                WHERE id = $1
                """,
                session["connector_id"],
            )

        # Update booking if exists
        if session.get("booking_id"):
            await conn.execute(
                """
                UPDATE bookings
                SET status = 'completed', updated_at = NOW()
                WHERE id = $1
                """,
                session["booking_id"],
            )

        # Create invoice
        invoice_row = await conn.fetchrow(
            """
            INSERT INTO invoices (
                user_id,
                session_id,
                amount,
                tax_amount,
                total_amount,
                status,
                due_date,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, 'pending', NOW() + INTERVAL '30 days', NOW())
            RETURNING *
            """,
            current_user["id"],
            session_id,
            amount,
            tax_amount,
            total_amount,
        )

        return {
            "session": dict(result_row),
            "invoice": dict(invoice_row),
        }


@router.get("")
async def list_my_sessions(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT
                ss.*,
                s.name AS station_name,
                s.address AS station_address,
                c.name AS connector_name,
                c.connector_type,
                c.power_type,
                c.max_power_kw,
                v.make AS vehicle_make,
                v.model AS vehicle_model,
                v.license_plate AS vehicle_license_plate
            FROM sessions ss
            JOIN stations s ON s.id = ss.station_id
            JOIN connectors c ON c.id = ss.connector_id
            LEFT JOIN vehicles v ON v.id = ss.vehicle_id
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
            SELECT
                ss.*,
                s.name AS station_name,
                s.address AS station_address,
                c.name AS connector_name,
                c.connector_type,
                c.power_type,
                c.max_power_kw,
                v.make AS vehicle_make,
                v.model AS vehicle_model,
                v.license_plate AS vehicle_license_plate
            FROM sessions ss
            JOIN stations s ON s.id = ss.station_id
            JOIN connectors c ON c.id = ss.connector_id
            LEFT JOIN vehicles v ON v.id = ss.vehicle_id
            WHERE ss.user_id = $1
              AND ss.status = 'active'
            ORDER BY ss.start_time DESC
            """,
            current_user["id"],
        )

        return [dict(r) for r in rows]

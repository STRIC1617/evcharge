from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from datetime import datetime, timedelta, timezone
import json

from config.database import get_pool
from middleware.auth import get_current_user

def ensure_utc(dt: datetime) -> datetime:
    """Convert datetime to naive UTC format for PostgreSQL."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Already naive, assume it's UTC
        return dt
    # Has timezone, convert to UTC and make naive
    return dt.astimezone(timezone.utc).replace(tzinfo=None)

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


class BookingRequest(BaseModel):
    vehicle_id: Optional[int] = None
    station_id: int
    connector_id: int
    charging_gun_id: Optional[int] = None
    fleet_id: Optional[int] = None
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
    """Create a booking for a charging session. Can optionally specify a charging gun."""
    # Convert times to UTC
    start_time = ensure_utc(request.start_time)
    end_time = ensure_utc(request.end_time)
    
    _validate_times(start_time, end_time)

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

        # Validate charging gun if specified
        charging_gun_id = request.charging_gun_id
        if charging_gun_id:
            gun_row = await conn.fetchrow(
                "SELECT id, status FROM charging_guns WHERE id = $1 AND connector_id = $2",
                charging_gun_id,
                request.connector_id,
            )
            if not gun_row:
                raise HTTPException(status_code=404, detail="Charging gun not found for this connector")
            
            if gun_row["status"] in ("offline", "maintenance"):
                raise HTTPException(status_code=400, detail=f"Charging gun is {gun_row['status']}")

        # Booking conflicts: check per-gun when a specific gun was requested (guns on the
        # same connector operate independently), otherwise fall back to the whole connector.
        if charging_gun_id:
            conflict_booking = await conn.fetchrow(
                """
                SELECT id FROM bookings
                WHERE charging_gun_id = $1
                  AND status IN ('pending', 'confirmed', 'in_progress')
                  AND NOT (end_time <= $2 OR start_time >= $3)
                LIMIT 1
                """,
                charging_gun_id,
                start_time,
                end_time,
            )
        else:
            conflict_booking = await conn.fetchrow(
                """
                SELECT id FROM bookings
                WHERE connector_id = $1
                  AND charging_gun_id IS NULL
                  AND status IN ('pending', 'confirmed', 'in_progress')
                  AND NOT (end_time <= $2 OR start_time >= $3)
                LIMIT 1
                """,
                request.connector_id,
                start_time,
                end_time,
            )
        if conflict_booking:
            raise HTTPException(status_code=400, detail="Time slot already booked")

        # Also block if there is an active session overlapping requested window
        if charging_gun_id:
            conflict_session = await conn.fetchrow(
                """
                SELECT id FROM sessions
                WHERE charging_gun_id = $1
                  AND status = 'active'
                  AND (
                    start_time <= $3
                    AND (end_time IS NULL OR end_time >= $2)
                  )
                LIMIT 1
                """,
                charging_gun_id,
                start_time,
                end_time,
            )
        else:
            conflict_session = await conn.fetchrow(
                """
                SELECT id FROM sessions
                WHERE connector_id = $1
                  AND charging_gun_id IS NULL
                  AND status = 'active'
                  AND (
                    start_time <= $3
                    AND (end_time IS NULL OR end_time >= $2)
                  )
                LIMIT 1
                """,
                request.connector_id,
                start_time,
                end_time,
            )
        if conflict_session:
            raise HTTPException(status_code=400, detail="Connector has an active session")

        # Verify fleet if specified
        if request.fleet_id:
            fleet = await conn.fetchrow(
                "SELECT id FROM fleet_members WHERE fleet_id = $1 AND user_id = $2",
                request.fleet_id,
                current_user["id"],
            )
            if not fleet:
                raise HTTPException(status_code=403, detail="You are not a member of this fleet")

        # Verify vehicle if specified
        if request.vehicle_id:
            vehicle = await conn.fetchrow(
                "SELECT id FROM vehicles WHERE id = $1",
                request.vehicle_id,
            )
            if not vehicle:
                raise HTTPException(status_code=404, detail="Vehicle not found")

        pricing_snapshot = {
            "price_per_kwh": float(connector["price_per_kwh"] or 0),
            "price_per_minute": float(connector["price_per_minute"] or 0),
            "max_power_kw": float(connector["max_power_kw"] or 0),
            "captured_at": datetime.utcnow().isoformat(),
        }

        row = await conn.fetchrow(
            """
            INSERT INTO bookings (user_id, fleet_id, vehicle_id, station_id, connector_id, charging_gun_id, start_time, end_time, pricing_snapshot, status, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, 'confirmed', NOW())
            RETURNING *
            """,
            current_user["id"],
            request.fleet_id,
            request.vehicle_id,
            request.station_id,
            request.connector_id,
            charging_gun_id,
            start_time,
            end_time,
            json.dumps(pricing_snapshot),
        )
        return dict(row)


@router.get("")
async def list_my_bookings(current_user: dict = Depends(get_current_user)):
    """List all bookings for the current user."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT b.*, s.name as station_name, s.address as station_address,
                   c.name as connector_name, c.connector_type, c.power_type, c.max_power_kw,
                   g.gun_name, g.qr_code, g.barcode_code
            FROM bookings b
            JOIN stations s ON s.id = b.station_id
            JOIN connectors c ON c.id = b.connector_id
            LEFT JOIN charging_guns g ON g.id = b.charging_gun_id
            WHERE b.user_id = $1
            ORDER BY b.start_time DESC
            """,
            current_user["id"],
        )
        return [dict(r) for r in rows]


@router.get("/{booking_id}")
async def get_booking(booking_id: int, current_user: dict = Depends(get_current_user)):
    """Get booking details."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT b.*, s.name as station_name, s.address as station_address,
                   c.name as connector_name, c.connector_type, c.power_type, c.max_power_kw,
                   g.gun_name, g.qr_code, g.barcode_code
            FROM bookings b
            JOIN stations s ON s.id = b.station_id
            JOIN connectors c ON c.id = b.connector_id
            LEFT JOIN charging_guns g ON g.id = b.charging_gun_id
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
    """Cancel a booking."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        booking = await conn.fetchrow(
            "SELECT id, status FROM bookings WHERE id = $1 AND user_id = $2",
            booking_id,
            current_user["id"],
        )
        
        if not booking:
            raise HTTPException(status_code=404, detail="Booking not found")
        
        if booking["status"] not in ("pending", "confirmed"):
            raise HTTPException(status_code=400, detail=f"Cannot cancel booking with status {booking['status']}")
        
        await conn.execute(
            "UPDATE bookings SET status = 'cancelled', updated_at = NOW() WHERE id = $1",
            booking_id,
        )
        
        return {"message": "Booking cancelled successfully"}


class StartSessionRequest(BaseModel):
    """Request to start a charging session by scanning QR/barcode."""
    qr_code: Optional[str] = None
    barcode_code: Optional[str] = None
    gun_id: Optional[int] = None
    vehicle_id: Optional[int] = None
    duration_minutes: int = 120  # Default 2 hours


@router.post("/session/start")
async def start_session(request: StartSessionRequest, current_user: dict = Depends(get_current_user)):
    """
    Start a charging session instantly by scanning QR/barcode or entering gun ID.
    Automatically creates booking with default 2-hour window.
    
    Usage:
    - Scan QR code: {"qr_code": "QR-JGD-1-1", "vehicle_id": 5}
    - Scan Barcode: {"barcode_code": "BC-JGD-1-1", "vehicle_id": 5}
    - Enter ID: {"gun_id": 1, "vehicle_id": 5}
    """
    
    # Validate at least one identifier provided
    if not request.qr_code and not request.barcode_code and not request.gun_id:
        raise HTTPException(status_code=400, detail="Must provide qr_code, barcode_code, or gun_id")
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Find the charging gun
        gun_row = None
        if request.qr_code:
            gun_row = await conn.fetchrow(
                "SELECT * FROM charging_guns WHERE qr_code = $1",
                request.qr_code,
            )
            if not gun_row:
                raise HTTPException(status_code=404, detail="Charging gun QR code not found")
        elif request.barcode_code:
            gun_row = await conn.fetchrow(
                "SELECT * FROM charging_guns WHERE barcode_code = $1",
                request.barcode_code,
            )
            if not gun_row:
                raise HTTPException(status_code=404, detail="Charging gun barcode code not found")
        elif request.gun_id:
            gun_row = await conn.fetchrow(
                "SELECT * FROM charging_guns WHERE id = $1",
                request.gun_id,
            )
            if not gun_row:
                raise HTTPException(status_code=404, detail="Charging gun not found")

        # Check gun status
        if gun_row["status"] in ("offline", "maintenance"):
            raise HTTPException(status_code=400, detail=f"Charging gun is {gun_row['status']}")

        connector_id = gun_row["connector_id"]

        # Get connector and station info
        connector_row = await conn.fetchrow(
            "SELECT * FROM connectors WHERE id = $1",
            connector_id,
        )
        if not connector_row:
            raise HTTPException(status_code=404, detail="Connector not found")

        station_id = connector_row["station_id"]

        # Check connector status
        if connector_row["status"] in ("offline", "maintenance"):
            raise HTTPException(status_code=400, detail=f"Connector is {connector_row['status']}")

        # Auto-calculate time window (now to now + duration)
        from datetime import datetime, timezone

        start_time = datetime.now(timezone.utc).replace(tzinfo=None)
        end_time = start_time + timedelta(minutes=request.duration_minutes)

        # Reuse an existing in-window booking for this user if present.
        booking_row = await conn.fetchrow(
            """
            SELECT * FROM bookings
            WHERE user_id = $1
              AND connector_id = $2
              AND status IN ('pending', 'confirmed', 'in_progress')
              AND start_time <= $3
              AND end_time >= $3
            ORDER BY
              CASE status
                WHEN 'in_progress' THEN 0
                WHEN 'confirmed' THEN 1
                ELSE 2
              END,
              start_time DESC
            LIMIT 1
            """,
            current_user["id"],
            connector_id,
            start_time,
        )

        # If no reusable booking exists for this user, fail when connector is already booked in-window.
        if not booking_row:
            conflict_booking = await conn.fetchrow(
                """
                SELECT id FROM bookings
                WHERE connector_id = $1
                  AND status IN ('pending', 'confirmed', 'in_progress')
                  AND NOT (end_time <= $2 OR start_time >= $3)
                LIMIT 1
                """,
                connector_id,
                start_time,
                end_time,
            )
            if conflict_booking:
                raise HTTPException(status_code=400, detail="Connector already has a booking in this time window")

        # Create pricing snapshot
        pricing_snapshot = {
            "price_per_kwh": float(connector_row["price_per_kwh"] or 0),
            "price_per_minute": float(connector_row["price_per_minute"] or 0),
            "max_power_kw": float(connector_row["max_power_kw"] or 0),
            "captured_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        }

        # Idempotent retry for same user: if an active session already exists, return it.
        conflict_session = await conn.fetchrow(
            """
            SELECT * FROM sessions
            WHERE connector_id = $1 AND status = 'active'
            ORDER BY start_time DESC
            LIMIT 1
            """,
            connector_id,
        )

        if conflict_session:
            if conflict_session["user_id"] != current_user["id"]:
                raise HTTPException(status_code=400, detail="Connector has an active charging session")

            if booking_row and booking_row["status"] != "in_progress":
                await conn.execute(
                    "UPDATE bookings SET status = 'in_progress', updated_at = NOW() WHERE id = $1",
                    booking_row["id"],
                )

            await conn.execute(
                "UPDATE charging_guns SET status = 'in_use', last_used_at = NOW() WHERE id = $1",
                gun_row["id"],
            )

            station_row = await conn.fetchrow("SELECT * FROM stations WHERE id = $1", station_id)

            return {
                "session_id": conflict_session["id"],
                "booking_id": booking_row["id"] if booking_row else conflict_session["booking_id"],
                "status": "charging_started",
                "gun": {
                    "id": gun_row["id"],
                    "gun_number": gun_row["gun_number"],
                    "gun_name": gun_row["gun_name"],
                    "qr_code": gun_row["qr_code"],
                    "barcode_code": gun_row["barcode_code"],
                },
                "connector": {
                    "id": connector_row["id"],
                    "name": connector_row["name"],
                    "connector_type": connector_row["connector_type"],
                    "power_type": connector_row["power_type"],
                    "max_power_kw": connector_row["max_power_kw"],
                },
                "station": {
                    "id": station_row["id"],
                    "name": station_row["name"],
                    "address": station_row["address"],
                    "operator_name": station_row["operator_name"],
                },
                "start_time": conflict_session["start_time"].isoformat() if conflict_session["start_time"] else start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_minutes": request.duration_minutes,
                "pricing": pricing_snapshot,
                "message": "Charging session already active for this connector",
            }

        if not booking_row:
            booking_row = await conn.fetchrow(
                """
                INSERT INTO bookings (user_id, station_id, connector_id, charging_gun_id, vehicle_id, start_time, end_time, pricing_snapshot, status, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'in_progress', NOW())
                RETURNING *
                """,
                current_user["id"],
                station_id,
                connector_id,
                gun_row["id"],
                request.vehicle_id,
                start_time,
                end_time,
                json.dumps(pricing_snapshot),
            )
        elif booking_row["status"] != "in_progress":
            await conn.execute(
                "UPDATE bookings SET status = 'in_progress', updated_at = NOW() WHERE id = $1",
                booking_row["id"],
            )

        # Create session record
        session_row = await conn.fetchrow(
            """
            INSERT INTO sessions (
                booking_id,
                station_id,
                connector_id,
                charging_gun_id,
                user_id,
                vehicle_id,
                start_time,
                tariff_snapshot,
                status,
                updated_at
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'active', NOW())
            RETURNING *
            """,
            booking_row["id"],
            station_id,
            connector_id,
            gun_row["id"],
            current_user["id"],
            request.vehicle_id,
            start_time,
            json.dumps(pricing_snapshot),
        )

        # Update gun status to in_use
        await conn.execute(
            "UPDATE charging_guns SET status = 'in_use', last_used_at = NOW() WHERE id = $1",
            gun_row["id"],
        )

        # Get full details for response
        station_row = await conn.fetchrow("SELECT * FROM stations WHERE id = $1", station_id)

        return {
            "session_id": session_row["id"],
            "booking_id": booking_row["id"],
            "status": "charging_started",
            "gun": {
                "id": gun_row["id"],
                "gun_number": gun_row["gun_number"],
                "gun_name": gun_row["gun_name"],
                "qr_code": gun_row["qr_code"],
                "barcode_code": gun_row["barcode_code"],
            },
            "connector": {
                "id": connector_row["id"],
                "name": connector_row["name"],
                "connector_type": connector_row["connector_type"],
                "power_type": connector_row["power_type"],
                "max_power_kw": connector_row["max_power_kw"],
            },
            "station": {
                "id": station_row["id"],
                "name": station_row["name"],
                "address": station_row["address"],
                "operator_name": station_row["operator_name"],
            },
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "duration_minutes": request.duration_minutes,
            "pricing": pricing_snapshot,
            "message": "✓ Charging session started successfully",
        }

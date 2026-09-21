from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime
import secrets

from config.database import get_pool, ensure_wallet
from middleware.auth import get_current_user, get_password_hash

router = APIRouter(prefix="/api/fleets", tags=["fleets"])


# ==================== Request/Response Models ====================

class FleetCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    billing_contact_name: Optional[str] = None
    billing_contact_email: Optional[EmailStr] = None
    billing_contact_phone: Optional[str] = None


class FleetUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    billing_contact_name: Optional[str] = None
    billing_contact_email: Optional[EmailStr] = None
    billing_contact_phone: Optional[str] = None


class FleetMemberAddRequest(BaseModel):
    user_id: int
    role: str = "driver"  # admin, manager, driver


class FleetVehicleAddRequest(BaseModel):
    vehicle_id: int
    assigned_to_user_id: Optional[int] = None
    is_shared: bool = False


class DriverRegisterRequest(BaseModel):
    email: EmailStr
    name: Optional[str] = None
    phone: Optional[str] = None
    role: str = "driver"  # manager or driver


class FleetVehicleRegisterRequest(BaseModel):
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    battery_capacity_kwh: Optional[float] = None
    connector_type: Optional[str] = None
    license_plate: Optional[str] = None
    vin: Optional[str] = None
    assigned_to_user_id: Optional[int] = None
    is_shared: bool = True


# ==================== Helper Functions ====================

async def _check_fleet_permission(conn, fleet_id: int, user_id: int, required_role: Optional[str] = None):
    """Check if user has access to fleet and has required role if specified."""
    member = await conn.fetchrow(
        """
        SELECT role FROM fleet_members
        WHERE fleet_id = $1 AND user_id = $2
        """,
        fleet_id,
        user_id,
    )
    
    if not member:
        raise HTTPException(status_code=403, detail="You do not have access to this fleet")
    
    if required_role and member["role"] not in ("admin",):
        if required_role == "manager" and member["role"] not in ("admin", "manager"):
            raise HTTPException(status_code=403, detail=f"This action requires {required_role} or higher role")
        elif required_role == "driver" and member["role"] == "driver":
            raise HTTPException(status_code=403, detail="Insufficient permissions for this action")
    
    return member["role"]


# ==================== Fleet CRUD ====================

@router.post("")
async def create_fleet(req: FleetCreateRequest, current_user: dict = Depends(get_current_user)):
    """Create a new fleet. Current user becomes the owner and admin."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Create fleet
        fleet = await conn.fetchrow(
            """
            INSERT INTO fleets (name, description, owner_id, billing_contact_name, 
                               billing_contact_email, billing_contact_phone)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, name, description, owner_id, billing_contact_name, 
                      billing_contact_email, billing_contact_phone, status, created_at, updated_at
            """,
            req.name,
            req.description,
            current_user["id"],
            req.billing_contact_name,
            req.billing_contact_email,
            req.billing_contact_phone,
        )
        
        # Add owner as admin member
        await conn.execute(
            """
            INSERT INTO fleet_members (fleet_id, user_id, role)
            VALUES ($1, $2, 'admin')
            """,
            fleet["id"],
            current_user["id"],
        )
        
        return dict(fleet)


@router.get("")
async def list_my_fleets(current_user: dict = Depends(get_current_user)):
    """List all fleets the current user is a member of."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT f.id, f.name, f.description, f.owner_id, f.billing_contact_name,
                   f.billing_contact_email, f.billing_contact_phone, f.status,
                   f.created_at, f.updated_at, fm.role
            FROM fleets f
            JOIN fleet_members fm ON f.id = fm.fleet_id
            WHERE fm.user_id = $1
            ORDER BY f.created_at DESC
            """,
            current_user["id"],
        )
        return [dict(r) for r in rows]


@router.get("/{fleet_id}")
async def get_fleet(fleet_id: int, current_user: dict = Depends(get_current_user)):
    """Get fleet details."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"])
        
        fleet = await conn.fetchrow(
            """
            SELECT id, name, description, owner_id, billing_contact_name,
                   billing_contact_email, billing_contact_phone, status,
                   created_at, updated_at
            FROM fleets
            WHERE id = $1
            """,
            fleet_id,
        )
        
        if not fleet:
            raise HTTPException(status_code=404, detail="Fleet not found")
        
        return dict(fleet)


@router.patch("/{fleet_id}")
async def update_fleet(fleet_id: int, req: FleetUpdateRequest, 
                       current_user: dict = Depends(get_current_user)):
    """Update fleet details. Only admins can update."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"], required_role="admin")
        
        fleet = await conn.fetchrow(
            """
            UPDATE fleets
            SET name = COALESCE($1, name),
                description = COALESCE($2, description),
                billing_contact_name = COALESCE($3, billing_contact_name),
                billing_contact_email = COALESCE($4, billing_contact_email),
                billing_contact_phone = COALESCE($5, billing_contact_phone),
                updated_at = NOW()
            WHERE id = $6
            RETURNING id, name, description, owner_id, billing_contact_name,
                      billing_contact_email, billing_contact_phone, status,
                      created_at, updated_at
            """,
            req.name,
            req.description,
            req.billing_contact_name,
            req.billing_contact_email,
            req.billing_contact_phone,
            fleet_id,
        )
        
        if not fleet:
            raise HTTPException(status_code=404, detail="Fleet not found")
        
        return dict(fleet)


@router.delete("/{fleet_id}")
async def delete_fleet(fleet_id: int, current_user: dict = Depends(get_current_user)):
    """Delete fleet. Only owner can delete."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        fleet = await conn.fetchrow(
            "SELECT owner_id FROM fleets WHERE id = $1",
            fleet_id,
        )
        
        if not fleet:
            raise HTTPException(status_code=404, detail="Fleet not found")
        
        if fleet["owner_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Only fleet owner can delete the fleet")
        
        await conn.execute("DELETE FROM fleets WHERE id = $1", fleet_id)
        
        return {"message": "Fleet deleted successfully"}


# ==================== Fleet Members ====================

@router.post("/{fleet_id}/members")
async def add_fleet_member(fleet_id: int, req: FleetMemberAddRequest, 
                          current_user: dict = Depends(get_current_user)):
    """Add member to fleet. Only admins can add members."""
    # Validate role
    if req.role not in ("admin", "manager", "driver"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be admin, manager, or driver")
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"], required_role="admin")
        
        # Check if user exists
        user = await conn.fetchrow("SELECT id FROM users WHERE id = $1", req.user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Check if already a member
        existing = await conn.fetchrow(
            "SELECT id FROM fleet_members WHERE fleet_id = $1 AND user_id = $2",
            fleet_id,
            req.user_id,
        )
        
        if existing:
            raise HTTPException(status_code=400, detail="User is already a member of this fleet")
        
        # Add member
        member = await conn.fetchrow(
            """
            INSERT INTO fleet_members (fleet_id, user_id, role)
            VALUES ($1, $2, $3)
            RETURNING id, fleet_id, user_id, role, joined_at, updated_at
            """,
            fleet_id,
            req.user_id,
            req.role,
        )
        
        return dict(member)


@router.get("/{fleet_id}/members")
async def list_fleet_members(fleet_id: int, current_user: dict = Depends(get_current_user)):
    """List all members of a fleet."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"])
        
        rows = await conn.fetch(
            """
            SELECT fm.id, fm.fleet_id, fm.user_id, fm.role, fm.joined_at, fm.updated_at,
                   u.email, u.name, u.phone
            FROM fleet_members fm
            JOIN users u ON fm.user_id = u.id
            WHERE fm.fleet_id = $1
            ORDER BY fm.joined_at DESC
            """,
            fleet_id,
        )
        
        return [dict(r) for r in rows]


@router.patch("/{fleet_id}/members/{user_id}")
async def update_fleet_member_role(fleet_id: int, user_id: int, 
                                   role: str = "driver",
                                   current_user: dict = Depends(get_current_user)):
    """Update member role. Only admins can update roles."""
    if role not in ("admin", "manager", "driver"):
        raise HTTPException(status_code=400, detail="Invalid role")
    
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"], required_role="admin")
        
        member = await conn.fetchrow(
            """
            UPDATE fleet_members
            SET role = $1, updated_at = NOW()
            WHERE fleet_id = $2 AND user_id = $3
            RETURNING id, fleet_id, user_id, role, joined_at, updated_at
            """,
            role,
            fleet_id,
            user_id,
        )
        
        if not member:
            raise HTTPException(status_code=404, detail="Member not found in this fleet")
        
        return dict(member)


@router.delete("/{fleet_id}/members/{user_id}")
async def remove_fleet_member(fleet_id: int, user_id: int, 
                             current_user: dict = Depends(get_current_user)):
    """Remove member from fleet. Only admins can remove members."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"], required_role="admin")
        
        # Can't remove owner
        fleet = await conn.fetchrow("SELECT owner_id FROM fleets WHERE id = $1", fleet_id)
        if fleet and fleet["owner_id"] == user_id:
            raise HTTPException(status_code=400, detail="Cannot remove fleet owner")
        
        result = await conn.execute(
            "DELETE FROM fleet_members WHERE fleet_id = $1 AND user_id = $2",
            fleet_id,
            user_id,
        )
        
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Member not found in this fleet")
        
        return {"message": "Member removed successfully"}


@router.post("/{fleet_id}/drivers")
async def register_fleet_driver(
    fleet_id: int, req: DriverRegisterRequest, current_user: dict = Depends(get_current_user)
):
    """Register (or attach an existing account as) a driver/manager for the fleet.

    If no user exists with the given email, a new account is created with a random
    temporary password (returned once so the fleet admin can share it with the driver).
    """
    if req.role not in ("manager", "driver"):
        raise HTTPException(status_code=400, detail="Invalid role. Must be manager or driver")

    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"], required_role="manager")

        user = await conn.fetchrow("SELECT * FROM users WHERE email = $1", req.email)
        is_new_account = False
        temp_password = None

        if not user:
            is_new_account = True
            temp_password = secrets.token_urlsafe(9)
            user = await conn.fetchrow(
                """
                INSERT INTO users (email, password_hash, name, phone, auth_provider)
                VALUES ($1, $2, $3, $4, 'email')
                RETURNING *
                """,
                req.email,
                get_password_hash(temp_password),
                req.name,
                req.phone,
            )
            await ensure_wallet(conn, user["id"])

        user = dict(user)

        existing_member = await conn.fetchrow(
            "SELECT id FROM fleet_members WHERE fleet_id = $1 AND user_id = $2",
            fleet_id,
            user["id"],
        )
        if existing_member:
            raise HTTPException(status_code=400, detail="User is already a member of this fleet")

        member = await conn.fetchrow(
            """
            INSERT INTO fleet_members (fleet_id, user_id, role)
            VALUES ($1, $2, $3)
            RETURNING id, fleet_id, user_id, role, joined_at, updated_at
            """,
            fleet_id,
            user["id"],
            req.role,
        )

        return {
            **dict(member),
            "email": user["email"],
            "name": user["name"],
            "phone": user["phone"],
            "is_new_account": is_new_account,
            "temp_password": temp_password,
        }


@router.get("/{fleet_id}/drivers")
async def list_fleet_drivers(fleet_id: int, current_user: dict = Depends(get_current_user)):
    """List drivers in the fleet along with their usage stats."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"])

        rows = await conn.fetch(
            """
            SELECT fm.id as membership_id, fm.user_id, fm.role, fm.joined_at,
                   u.email, u.name, u.phone,
                   COUNT(s.id) FILTER (WHERE s.status = 'completed') as total_sessions,
                   COALESCE(SUM(s.energy_kwh) FILTER (WHERE s.status = 'completed'), 0) as total_energy_kwh,
                   COALESCE(SUM(s.cost) FILTER (WHERE s.status = 'completed'), 0) as total_cost
            FROM fleet_members fm
            JOIN users u ON u.id = fm.user_id
            LEFT JOIN sessions s ON s.user_id = fm.user_id AND s.fleet_id = fm.fleet_id
            WHERE fm.fleet_id = $1 AND fm.role = 'driver'
            GROUP BY fm.id, fm.user_id, fm.role, fm.joined_at, u.email, u.name, u.phone
            ORDER BY fm.joined_at DESC
            """,
            fleet_id,
        )

        return [
            {
                **{k: v for k, v in dict(r).items() if k not in ("total_energy_kwh", "total_cost")},
                "total_energy_kwh": float(r["total_energy_kwh"] or 0),
                "total_cost": float(r["total_cost"] or 0),
            }
            for r in rows
        ]


# ==================== Fleet Vehicles ====================

@router.post("/{fleet_id}/vehicles")
async def add_vehicle_to_fleet(fleet_id: int, req: FleetVehicleAddRequest, 
                              current_user: dict = Depends(get_current_user)):
    """Add a vehicle to fleet. Only managers/admins can add vehicles."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"], required_role="manager")
        
        # Check vehicle exists
        vehicle = await conn.fetchrow(
            "SELECT id, user_id FROM vehicles WHERE id = $1",
            req.vehicle_id,
        )
        
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        
        # Check if vehicle already in fleet
        existing = await conn.fetchrow(
            "SELECT id FROM fleet_vehicles WHERE fleet_id = $1 AND vehicle_id = $2",
            fleet_id,
            req.vehicle_id,
        )
        
        if existing:
            raise HTTPException(status_code=400, detail="Vehicle is already in this fleet")
        
        # If assigning to specific user, verify they're a fleet member
        if req.assigned_to_user_id:
            member = await conn.fetchrow(
                "SELECT id FROM fleet_members WHERE fleet_id = $1 AND user_id = $2",
                fleet_id,
                req.assigned_to_user_id,
            )
            if not member:
                raise HTTPException(status_code=400, detail="User is not a member of this fleet")
        
        # Add vehicle to fleet
        fleet_vehicle = await conn.fetchrow(
            """
            INSERT INTO fleet_vehicles (fleet_id, vehicle_id, assigned_to_user_id, is_shared)
            VALUES ($1, $2, $3, $4)
            RETURNING id, fleet_id, vehicle_id, assigned_to_user_id, is_shared, status, added_at, updated_at
            """,
            fleet_id,
            req.vehicle_id,
            req.assigned_to_user_id,
            req.is_shared,
        )
        
        return dict(fleet_vehicle)


@router.post("/{fleet_id}/vehicles/register")
async def register_fleet_vehicle(
    fleet_id: int, req: FleetVehicleRegisterRequest, current_user: dict = Depends(get_current_user)
):
    """Register a brand-new vehicle directly into the fleet (no pre-existing vehicle required)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"], required_role="manager")

        if req.assigned_to_user_id:
            member = await conn.fetchrow(
                "SELECT id FROM fleet_members WHERE fleet_id = $1 AND user_id = $2",
                fleet_id,
                req.assigned_to_user_id,
            )
            if not member:
                raise HTTPException(status_code=400, detail="User is not a member of this fleet")

        vehicle = await conn.fetchrow(
            """
            INSERT INTO vehicles (user_id, make, model, year, battery_capacity_kwh,
                                   connector_type, license_plate, vin, vehicle_type)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'fleet')
            RETURNING *
            """,
            req.assigned_to_user_id,
            req.make,
            req.model,
            req.year,
            req.battery_capacity_kwh,
            req.connector_type,
            req.license_plate,
            req.vin,
        )

        fleet_vehicle = await conn.fetchrow(
            """
            INSERT INTO fleet_vehicles (fleet_id, vehicle_id, assigned_to_user_id, is_shared)
            VALUES ($1, $2, $3, $4)
            RETURNING id, fleet_id, vehicle_id, assigned_to_user_id, is_shared, status, added_at, updated_at
            """,
            fleet_id,
            vehicle["id"],
            req.assigned_to_user_id,
            req.is_shared,
        )

        return {"vehicle": dict(vehicle), "fleet_vehicle": dict(fleet_vehicle)}


@router.get("/{fleet_id}/vehicles")
async def list_fleet_vehicles(fleet_id: int, current_user: dict = Depends(get_current_user)):
    """List all vehicles in a fleet."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"])
        
        rows = await conn.fetch(
            """
            SELECT fv.id, fv.fleet_id, fv.vehicle_id, fv.assigned_to_user_id, 
                   fv.is_shared, fv.status, fv.added_at, fv.updated_at,
                   v.make, v.model, v.year, v.battery_capacity_kwh, v.connector_type, 
                   v.license_plate, u.name as assigned_to_name
            FROM fleet_vehicles fv
            JOIN vehicles v ON fv.vehicle_id = v.id
            LEFT JOIN users u ON fv.assigned_to_user_id = u.id
            WHERE fv.fleet_id = $1
            ORDER BY fv.added_at DESC
            """,
            fleet_id,
        )
        
        return [dict(r) for r in rows]


@router.patch("/{fleet_id}/vehicles/{vehicle_id}")
async def update_fleet_vehicle(fleet_id: int, vehicle_id: int,
                              assigned_to_user_id: Optional[int] = None,
                              is_shared: Optional[bool] = None,
                              current_user: dict = Depends(get_current_user)):
    """Update fleet vehicle assignment. Only managers/admins can update."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"], required_role="manager")
        
        # Verify user is fleet member if assigned
        if assigned_to_user_id:
            member = await conn.fetchrow(
                "SELECT id FROM fleet_members WHERE fleet_id = $1 AND user_id = $2",
                fleet_id,
                assigned_to_user_id,
            )
            if not member:
                raise HTTPException(status_code=400, detail="User is not a member of this fleet")
        
        fleet_vehicle = await conn.fetchrow(
            """
            UPDATE fleet_vehicles
            SET assigned_to_user_id = COALESCE($1, assigned_to_user_id),
                is_shared = COALESCE($2, is_shared),
                updated_at = NOW()
            WHERE fleet_id = $3 AND vehicle_id = $4
            RETURNING id, fleet_id, vehicle_id, assigned_to_user_id, is_shared, status, added_at, updated_at
            """,
            assigned_to_user_id,
            is_shared,
            fleet_id,
            vehicle_id,
        )
        
        if not fleet_vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found in this fleet")
        
        return dict(fleet_vehicle)


@router.delete("/{fleet_id}/vehicles/{vehicle_id}")
async def remove_vehicle_from_fleet(fleet_id: int, vehicle_id: int,
                                   current_user: dict = Depends(get_current_user)):
    """Remove vehicle from fleet. Only managers/admins can remove."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"], required_role="manager")
        
        result = await conn.execute(
            "DELETE FROM fleet_vehicles WHERE fleet_id = $1 AND vehicle_id = $2",
            fleet_id,
            vehicle_id,
        )
        
        if result == "DELETE 0":
            raise HTTPException(status_code=404, detail="Vehicle not found in this fleet")
        
        return {"message": "Vehicle removed from fleet successfully"}


# ==================== Fleet Billing ====================

@router.get("/{fleet_id}/invoices")
async def get_fleet_invoices(fleet_id: int, current_user: dict = Depends(get_current_user)):
    """Get all invoices for a fleet."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"])
        
        rows = await conn.fetch(
            """
            SELECT id, fleet_id, billing_period_start, billing_period_end, 
                   total_sessions, total_energy_kwh, amount, tax_amount, 
                   total_amount, status, due_date, paid_at, created_at, updated_at
            FROM fleet_invoices
            WHERE fleet_id = $1
            ORDER BY billing_period_end DESC
            """,
            fleet_id,
        )
        
        return [dict(r) for r in rows]


@router.get("/{fleet_id}/stats")
async def get_fleet_stats(fleet_id: int, current_user: dict = Depends(get_current_user)):
    """Get fleet statistics (sessions, energy, costs)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"])
        
        # Get statistics
        stats = await conn.fetchrow(
            """
            SELECT 
                COUNT(DISTINCT s.id) as total_sessions,
                COALESCE(SUM(s.energy_kwh), 0) as total_energy_kwh,
                COALESCE(SUM(s.cost), 0) as total_cost,
                COUNT(DISTINCT s.user_id) as unique_drivers,
                COUNT(DISTINCT s.vehicle_id) as vehicles_used
            FROM sessions s
            WHERE s.fleet_id = $1 AND s.status = 'completed'
            """,
            fleet_id,
        )
        
        return {
            "fleet_id": fleet_id,
            "total_sessions": stats["total_sessions"] or 0,
            "total_energy_kwh": float(stats["total_energy_kwh"] or 0),
            "total_cost": float(stats["total_cost"] or 0),
            "unique_drivers": stats["unique_drivers"] or 0,
            "vehicles_used": stats["vehicles_used"] or 0,
        }


@router.get("/{fleet_id}/dashboard")
async def get_fleet_dashboard(fleet_id: int, current_user: dict = Depends(get_current_user)):
    """One-call summary for the fleet owner home screen/menu."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"])

        member_counts = await conn.fetch(
            "SELECT role, COUNT(*) as count FROM fleet_members WHERE fleet_id = $1 GROUP BY role",
            fleet_id,
        )
        vehicle_count = await conn.fetchval(
            "SELECT COUNT(*) FROM fleet_vehicles WHERE fleet_id = $1", fleet_id
        )
        active_sessions = await conn.fetchval(
            "SELECT COUNT(*) FROM sessions WHERE fleet_id = $1 AND status = 'active'", fleet_id
        )
        pending_invoices = await conn.fetchrow(
            """
            SELECT COUNT(*) as count, COALESCE(SUM(total_amount), 0) as amount
            FROM fleet_invoices WHERE fleet_id = $1 AND status = 'pending'
            """,
            fleet_id,
        )
        recent_sessions = await conn.fetch(
            """
            SELECT s.id, s.user_id, u.name as driver_name, s.vehicle_id, s.status,
                   s.energy_kwh, s.cost, s.start_time, s.end_time
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.fleet_id = $1
            ORDER BY s.start_time DESC
            LIMIT 10
            """,
            fleet_id,
        )

        return {
            "fleet_id": fleet_id,
            "member_counts": {r["role"]: r["count"] for r in member_counts},
            "vehicle_count": vehicle_count or 0,
            "active_sessions": active_sessions or 0,
            "pending_invoices": {
                "count": pending_invoices["count"] or 0,
                "amount": float(pending_invoices["amount"] or 0),
            },
            "recent_sessions": [dict(r) for r in recent_sessions],
        }


@router.get("/{fleet_id}/drivers/{user_id}/stats")
async def get_fleet_driver_stats(
    fleet_id: int, user_id: int, current_user: dict = Depends(get_current_user)
):
    """Detailed usage statistics for a single driver within the fleet."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"])

        member = await conn.fetchrow(
            """
            SELECT fm.id, fm.role, fm.joined_at, u.name, u.email, u.phone
            FROM fleet_members fm
            JOIN users u ON u.id = fm.user_id
            WHERE fm.fleet_id = $1 AND fm.user_id = $2
            """,
            fleet_id,
            user_id,
        )
        if not member:
            raise HTTPException(status_code=404, detail="Driver not found in this fleet")

        summary = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed') as total_sessions,
                COUNT(*) FILTER (WHERE status = 'active') as active_sessions,
                COALESCE(SUM(energy_kwh) FILTER (WHERE status = 'completed'), 0) as total_energy_kwh,
                COALESCE(SUM(cost) FILTER (WHERE status = 'completed'), 0) as total_cost,
                COUNT(DISTINCT vehicle_id) FILTER (WHERE status = 'completed') as vehicles_used
            FROM sessions
            WHERE fleet_id = $1 AND user_id = $2
            """,
            fleet_id,
            user_id,
        )

        recent_sessions = await conn.fetch(
            """
            SELECT s.id, s.vehicle_id, v.make, v.model, v.license_plate,
                   s.status, s.energy_kwh, s.cost, s.start_time, s.end_time
            FROM sessions s
            LEFT JOIN vehicles v ON v.id = s.vehicle_id
            WHERE s.fleet_id = $1 AND s.user_id = $2
            ORDER BY s.start_time DESC
            LIMIT 20
            """,
            fleet_id,
            user_id,
        )

        return {
            "fleet_id": fleet_id,
            "user_id": user_id,
            "name": member["name"],
            "email": member["email"],
            "phone": member["phone"],
            "role": member["role"],
            "joined_at": member["joined_at"],
            "total_sessions": summary["total_sessions"] or 0,
            "active_sessions": summary["active_sessions"] or 0,
            "total_energy_kwh": float(summary["total_energy_kwh"] or 0),
            "total_cost": float(summary["total_cost"] or 0),
            "vehicles_used": summary["vehicles_used"] or 0,
            "recent_sessions": [dict(r) for r in recent_sessions],
        }


@router.get("/{fleet_id}/vehicles/{vehicle_id}/stats")
async def get_fleet_vehicle_stats(
    fleet_id: int, vehicle_id: int, current_user: dict = Depends(get_current_user)
):
    """Detailed usage statistics for a single vehicle within the fleet."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await _check_fleet_permission(conn, fleet_id, current_user["id"])

        fleet_vehicle = await conn.fetchrow(
            """
            SELECT fv.assigned_to_user_id, fv.is_shared, fv.status as fleet_status,
                   v.make, v.model, v.year, v.battery_capacity_kwh, v.connector_type,
                   v.license_plate, v.vin
            FROM fleet_vehicles fv
            JOIN vehicles v ON v.id = fv.vehicle_id
            WHERE fv.fleet_id = $1 AND fv.vehicle_id = $2
            """,
            fleet_id,
            vehicle_id,
        )
        if not fleet_vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found in this fleet")

        summary = await conn.fetchrow(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'completed') as total_sessions,
                COUNT(*) FILTER (WHERE status = 'active') as active_sessions,
                COALESCE(SUM(energy_kwh) FILTER (WHERE status = 'completed'), 0) as total_energy_kwh,
                COALESCE(SUM(cost) FILTER (WHERE status = 'completed'), 0) as total_cost,
                COUNT(DISTINCT user_id) FILTER (WHERE status = 'completed') as unique_drivers
            FROM sessions
            WHERE fleet_id = $1 AND vehicle_id = $2
            """,
            fleet_id,
            vehicle_id,
        )

        recent_sessions = await conn.fetch(
            """
            SELECT s.id, s.user_id, u.name as driver_name,
                   s.status, s.energy_kwh, s.cost, s.start_time, s.end_time
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.fleet_id = $1 AND s.vehicle_id = $2
            ORDER BY s.start_time DESC
            LIMIT 20
            """,
            fleet_id,
            vehicle_id,
        )

        return {
            "fleet_id": fleet_id,
            "vehicle_id": vehicle_id,
            **dict(fleet_vehicle),
            "total_sessions": summary["total_sessions"] or 0,
            "active_sessions": summary["active_sessions"] or 0,
            "total_energy_kwh": float(summary["total_energy_kwh"] or 0),
            "total_cost": float(summary["total_cost"] or 0),
            "unique_drivers": summary["unique_drivers"] or 0,
            "recent_sessions": [dict(r) for r in recent_sessions],
        }

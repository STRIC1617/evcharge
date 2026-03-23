from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import json

from config.database import get_pool

router = APIRouter(prefix="/api/stations", tags=["stations"])


def _parse_json(val):
    if val is None:
        return None
    return json.loads(val) if isinstance(val, str) else val


def _validate_lat_lng(lat: float, lng: float):
    if lat < -90 or lat > 90 or lng < -180 or lng > 180:
        raise HTTPException(status_code=400, detail="Invalid lat/lng")


@router.get("")
async def list_stations(
    connector_type: Optional[str] = None,
    power_type: Optional[str] = None,
    include_connectors: bool = False,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List active stations. For performance, connectors are excluded unless include_connectors=true."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        base_where = "WHERE s.status = 'active'"
        params = []
        pc = 0

        if connector_type:
            pc += 1
            base_where += f" AND EXISTS (SELECT 1 FROM connectors cx WHERE cx.station_id = s.id AND cx.connector_type = ${pc})"
            params.append(connector_type)
        if power_type:
            pc += 1
            base_where += f" AND EXISTS (SELECT 1 FROM connectors cy WHERE cy.station_id = s.id AND cy.power_type = ${pc})"
            params.append(power_type)

        pc += 1
        params.append(limit)
        limit_param = pc
        pc += 1
        params.append(offset)
        offset_param = pc

        if include_connectors:
            query = f"""
                SELECT s.*,
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'id', c.id,
                                'name', c.name,
                                'connector_type', c.connector_type,
                                'power_type', c.power_type,
                                'max_power_kw', c.max_power_kw,
                                'price_per_kwh', c.price_per_kwh,
                                'price_per_minute', c.price_per_minute,
                                'status', c.status
                            )
                        ) FILTER (WHERE c.id IS NOT NULL),
                        '[]'::json
                    ) AS connectors
                FROM stations s
                LEFT JOIN connectors c ON c.station_id = s.id
                {base_where}
                GROUP BY s.id
                ORDER BY s.name
                LIMIT ${limit_param} OFFSET ${offset_param}
            """
            rows = await conn.fetch(query, *params)
            out = []
            for r in rows:
                d = dict(r)
                d["connectors"] = _parse_json(d.get("connectors")) or []
                out.append(d)
            return out

        # Without connectors
        query = f"""
            SELECT s.*
            FROM stations s
            {base_where}
            ORDER BY s.name
            LIMIT ${limit_param} OFFSET ${offset_param}
        """
        rows = await conn.fetch(query, *params)
        return [dict(r) for r in rows]


@router.get("/nearby")
async def nearby_stations(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(25, gt=0, le=200),
    include_connectors: bool = False,
    limit: int = Query(50, ge=1, le=200),
):
    """Nearby stations using Haversine. For production scale, move to PostGIS."""
    _validate_lat_lng(lat, lng)

    pool = await get_pool()
    async with pool.acquire() as conn:
        if include_connectors:
            rows = await conn.fetch(
                """
                SELECT s.*,
                    (6371 * acos(
                        cos(radians($1)) * cos(radians(latitude)) *
                        cos(radians(longitude) - radians($2)) +
                        sin(radians($1)) * sin(radians(latitude))
                    )) AS distance_km,
                    COALESCE(
                        json_agg(
                            json_build_object(
                                'id', c.id,
                                'name', c.name,
                                'connector_type', c.connector_type,
                                'power_type', c.power_type,
                                'max_power_kw', c.max_power_kw,
                                'price_per_kwh', c.price_per_kwh,
                                'price_per_minute', c.price_per_minute,
                                'status', c.status
                            )
                        ) FILTER (WHERE c.id IS NOT NULL),
                        '[]'::json
                    ) AS connectors
                FROM stations s
                LEFT JOIN connectors c ON c.station_id = s.id
                WHERE s.status = 'active'
                GROUP BY s.id
                HAVING (6371 * acos(
                    cos(radians($1)) * cos(radians(latitude)) *
                    cos(radians(longitude) - radians($2)) +
                    sin(radians($1)) * sin(radians(latitude))
                )) < $3
                ORDER BY distance_km
                LIMIT $4
                """,
                lat,
                lng,
                radius_km,
                limit,
            )
            out = []
            for r in rows:
                d = dict(r)
                d["connectors"] = _parse_json(d.get("connectors")) or []
                out.append(d)
            return out

        rows = await conn.fetch(
            """
            SELECT s.*,
                (6371 * acos(
                    cos(radians($1)) * cos(radians(latitude)) *
                    cos(radians(longitude) - radians($2)) +
                    sin(radians($1)) * sin(radians(latitude))
                )) AS distance_km
            FROM stations s
            WHERE s.status = 'active'
            AND (6371 * acos(
                cos(radians($1)) * cos(radians(latitude)) *
                cos(radians(longitude) - radians($2)) +
                sin(radians($1)) * sin(radians(latitude))
            )) < $3
            ORDER BY distance_km
            LIMIT $4
            """,
            lat,
            lng,
            radius_km,
            limit,
        )
        return [dict(r) for r in rows]


# Backward-compatible path-param route
@router.get("/nearby/{lat}/{lng}")
async def nearby_stations_legacy(lat: float, lng: float, radius: float = 25):
    return await nearby_stations(lat=lat, lng=lng, radius_km=radius, include_connectors=True, limit=50)


@router.get("/{station_id}")
async def get_station(station_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        station_row = await conn.fetchrow("SELECT * FROM stations WHERE id = $1", station_id)
        if not station_row:
            raise HTTPException(status_code=404, detail="Station not found")

        connector_rows = await conn.fetch(
            "SELECT * FROM connectors WHERE station_id = $1 ORDER BY id",
            station_id,
        )

        station = dict(station_row)
        station["connectors"] = [dict(r) for r in connector_rows]
        return station


@router.get("/{station_id}/connectors")
async def get_connectors(station_id: int):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM connectors WHERE station_id = $1 ORDER BY id", station_id)
        return [dict(r) for r in rows]

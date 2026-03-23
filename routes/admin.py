from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional

from config.database import get_pool
from middleware.auth import require_role

router = APIRouter(prefix="/api/admin", tags=["admin"])


class BannerCreateRequest(BaseModel):
    title: str
    subtitle: Optional[str] = None
    image_url: str
    cta_text: Optional[str] = None
    cta_action: Optional[str] = None
    priority: int = 0
    is_active: bool = True
    start_at: Optional[str] = None  # ISO string
    end_at: Optional[str] = None
    target_role: str = "all"
    target_city: Optional[str] = None
    target_state: Optional[str] = None
    min_app_version: Optional[str] = None
    max_app_version: Optional[str] = None


class BannerUpdateRequest(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    image_url: Optional[str] = None
    cta_text: Optional[str] = None
    cta_action: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    target_role: Optional[str] = None
    target_city: Optional[str] = None
    target_state: Optional[str] = None
    min_app_version: Optional[str] = None
    max_app_version: Optional[str] = None


@router.get("/banners")
async def list_banners(
    is_active: Optional[bool] = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(require_role("admin", "superadmin")),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        if is_active is None:
            rows = await conn.fetch(
                "SELECT * FROM home_banners ORDER BY priority DESC, id DESC LIMIT $1",
                limit,
            )
        else:
            rows = await conn.fetch(
                "SELECT * FROM home_banners WHERE is_active = $1 ORDER BY priority DESC, id DESC LIMIT $2",
                is_active,
                limit,
            )
        return [dict(r) for r in rows]


@router.post("/banners")
async def create_banner(
    req: BannerCreateRequest,
    current_user: dict = Depends(require_role("admin", "superadmin")),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            INSERT INTO home_banners (
                title, subtitle, image_url, cta_text, cta_action,
                priority, is_active, start_at, end_at,
                target_role, target_city, target_state,
                min_app_version, max_app_version,
                created_by, updated_at
            )
            VALUES (
                $1,$2,$3,$4,$5,
                $6,$7,$8::timestamp,$9::timestamp,
                $10,$11,$12,
                $13,$14,
                $15, NOW()
            )
            RETURNING *
            """,
            req.title,
            req.subtitle,
            req.image_url,
            req.cta_text,
            req.cta_action,
            req.priority,
            req.is_active,
            req.start_at,
            req.end_at,
            req.target_role,
            req.target_city,
            req.target_state,
            req.min_app_version,
            req.max_app_version,
            current_user["id"],
        )
        return dict(row)


@router.patch("/banners/{banner_id}")
async def update_banner(
    banner_id: int,
    req: BannerUpdateRequest,
    current_user: dict = Depends(require_role("admin", "superadmin")),
):
    pool = await get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchrow("SELECT id FROM home_banners WHERE id = $1", banner_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Banner not found")

        row = await conn.fetchrow(
            """
            UPDATE home_banners SET
              title = COALESCE($1, title),
              subtitle = COALESCE($2, subtitle),
              image_url = COALESCE($3, image_url),
              cta_text = COALESCE($4, cta_text),
              cta_action = COALESCE($5, cta_action),
              priority = COALESCE($6, priority),
              is_active = COALESCE($7, is_active),
              start_at = COALESCE($8::timestamp, start_at),
              end_at = COALESCE($9::timestamp, end_at),
              target_role = COALESCE($10, target_role),
              target_city = COALESCE($11, target_city),
              target_state = COALESCE($12, target_state),
              min_app_version = COALESCE($13, min_app_version),
              max_app_version = COALESCE($14, max_app_version),
              updated_at = NOW()
            WHERE id = $15
            RETURNING *
            """,
            req.title,
            req.subtitle,
            req.image_url,
            req.cta_text,
            req.cta_action,
            req.priority,
            req.is_active,
            req.start_at,
            req.end_at,
            req.target_role,
            req.target_city,
            req.target_state,
            req.min_app_version,
            req.max_app_version,
            banner_id,
        )
        return dict(row)

from fastapi import APIRouter, Query
from typing import Optional

from config.database import get_pool

router = APIRouter(prefix="/api/content", tags=["content"])


def _version_in_range(app_version: Optional[str], min_v: Optional[str], max_v: Optional[str]) -> bool:
    # Simple string compare fallback; production should use semantic version parser
    if not app_version:
        return True
    if min_v and app_version < min_v:
        return False
    if max_v and app_version > max_v:
        return False
    return True


@router.get("/home-banners")
async def list_home_banners(
    role: str = Query("all"),
    city: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    app_version: Optional[str] = Query(default=None),
    limit: int = Query(10, ge=1, le=25),
):
    """Dynamic banners for home screen.

    Filter logic:
    - active now (start/end)
    - target_role matches role or 'all'
    - optional city/state match if banner targets them
    - optional app version gating
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT * FROM home_banners
            WHERE is_active = true
              AND (start_at IS NULL OR start_at <= NOW())
              AND (end_at IS NULL OR end_at >= NOW())
              AND (target_role = 'all' OR target_role = $1)
              AND (target_city IS NULL OR target_city = $2)
              AND (target_state IS NULL OR target_state = $3)
            ORDER BY priority DESC, id DESC
            LIMIT $4
            """,
            role,
            city,
            state,
            limit,
        )

        out = []
        for r in rows:
            d = dict(r)
            if not _version_in_range(app_version, d.get("min_app_version"), d.get("max_app_version")):
                continue
            out.append(
                {
                    "id": d["id"],
                    "title": d["title"],
                    "subtitle": d.get("subtitle"),
                    "image_url": d["image_url"],
                    "cta_text": d.get("cta_text"),
                    "cta_action": d.get("cta_action"),
                    "priority": d.get("priority", 0),
                }
            )
        return {"banners": out}

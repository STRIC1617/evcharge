from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from datetime import datetime
import secrets

from config.database import get_pool
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/billing", tags=["billing"])


class PaymentRequest(BaseModel):
    payment_method: str


@router.get("/invoices")
async def list_invoices(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT i.*, s.station_name, s.energy_kwh, s.start_time as session_start, s.end_time as session_end
            FROM invoices i
            LEFT JOIN (
                SELECT ss.id, st.name as station_name, ss.energy_kwh, ss.start_time, ss.end_time
                FROM sessions ss
                JOIN stations st ON st.id = ss.station_id
            ) s ON s.id = i.session_id
            WHERE i.user_id = $1
            ORDER BY i.created_at DESC
            """,
            current_user["id"],
        )
        return [dict(r) for r in rows]


@router.get("/invoices/{invoice_id}")
async def get_invoice(invoice_id: int, current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT i.*, s.station_name, s.energy_kwh, s.start_time as session_start, s.end_time as session_end,
                s.connector_name, s.connector_type
            FROM invoices i
            LEFT JOIN (
                SELECT ss.id, st.name as station_name, ss.energy_kwh, ss.start_time, ss.end_time,
                    c.name as connector_name, c.connector_type
                FROM sessions ss
                JOIN stations st ON st.id = ss.station_id
                JOIN connectors c ON c.id = ss.connector_id
            ) s ON s.id = i.session_id
            WHERE i.id = $1 AND i.user_id = $2
            """,
            invoice_id,
            current_user["id"],
        )
        if not row:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return dict(row)


@router.get("/payments")
async def list_payments(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT p.*, i.total_amount as invoice_total
            FROM payments p
            JOIN invoices i ON i.id = p.invoice_id
            WHERE p.user_id = $1
            ORDER BY p.created_at DESC
            """,
            current_user["id"],
        )
        return [dict(r) for r in rows]


@router.post("/pay/{invoice_id}")
async def pay_invoice(invoice_id: int, request: PaymentRequest, current_user: dict = Depends(get_current_user)):
    """Mock payment endpoint.

    In production:
    - Create a payment intent with gateway
    - Update status asynchronously via webhook
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        invoice_row = await conn.fetchrow(
            "SELECT * FROM invoices WHERE id = $1 AND user_id = $2",
            invoice_id,
            current_user["id"],
        )
        if not invoice_row:
            raise HTTPException(status_code=404, detail="Invoice not found")

        invoice = dict(invoice_row)
        if invoice["status"] == "paid":
            raise HTTPException(status_code=400, detail="Invoice already paid")

        transaction_id = f"TXN_{int(datetime.utcnow().timestamp())}_{secrets.token_hex(4)}"

        payment_row = await conn.fetchrow(
            """
            INSERT INTO payments (invoice_id, user_id, amount, payment_method, transaction_id, status, updated_at)
            VALUES ($1, $2, $3, $4, $5, 'completed', NOW())
            RETURNING *
            """,
            invoice_id,
            current_user["id"],
            invoice["total_amount"],
            request.payment_method,
            transaction_id,
        )

        await conn.execute(
            "UPDATE invoices SET status = 'paid', paid_at = NOW(), updated_at = NOW() WHERE id = $1",
            invoice_id,
        )

        return {"payment": dict(payment_row), "message": "Payment successful"}


@router.get("/tariffs")
async def list_tariffs():
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM tariffs ORDER BY name")
        return [dict(r) for r in rows]


@router.get("/summary")
async def billing_summary(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        sessions_row = await conn.fetchrow(
            """
            SELECT COUNT(*) as total_sessions, COALESCE(SUM(energy_kwh), 0) as total_energy,
                COALESCE(SUM(cost), 0) as total_spent
            FROM sessions WHERE user_id = $1 AND status = 'completed'
            """,
            current_user["id"],
        )

        invoices_row = await conn.fetchrow(
            """
            SELECT COUNT(*) FILTER (WHERE status = 'pending') as pending_invoices,
                COALESCE(SUM(total_amount) FILTER (WHERE status = 'pending'), 0) as pending_amount
            FROM invoices WHERE user_id = $1
            """,
            current_user["id"],
        )

        return {**dict(sessions_row), **dict(invoices_row)}

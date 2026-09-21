import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from datetime import datetime
import secrets

from config.database import get_pool, ensure_wallet
from config.phonepe_client import (
    check_status as check_phonepe_status,
    create_payment as create_phonepe_payment,
    decode_callback_payload,
    new_merchant_transaction_id,
    verify_callback_signature,
)
from middleware.auth import get_current_user

router = APIRouter(prefix="/api/billing", tags=["billing"])


class PaymentRequest(BaseModel):
    payment_method: str


class WalletTopupRequest(BaseModel):
    amount: float = Field(gt=0)


async def _get_or_create_wallet(conn, user_id: int) -> dict:
    return await ensure_wallet(conn, user_id)


def _phonepe_configured() -> bool:
    return bool(os.getenv("PHONEPE_MERCHANT_ID") and os.getenv("PHONEPE_SALT_KEY"))


def _allow_direct_credit_fallback() -> bool:
    """True when PhonePe isn't configured and we're not in production (local/dev testing)."""
    if _phonepe_configured():
        return False
    return os.getenv("PHONEPE_ENV", "sandbox").lower() != "production"


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
    """Pay an invoice using wallet balance.

    For card/UPI/netbanking payments, use POST /invoices/{invoice_id}/order to get a
    PhonePe checkout redirect URL instead.
    """
    if request.payment_method != "wallet":
        raise HTTPException(
            status_code=400,
            detail="Set payment_method='wallet', or use /invoices/{invoice_id}/order for card/UPI/netbanking",
        )

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

        amount = float(invoice["total_amount"])

        async with conn.transaction():
            wallet = await _get_or_create_wallet(conn, current_user["id"])
            if float(wallet["balance"]) < amount:
                raise HTTPException(status_code=400, detail="Insufficient wallet balance")

            new_balance = float(wallet["balance"]) - amount
            transaction_id = f"TXN_{int(datetime.utcnow().timestamp())}_{secrets.token_hex(4)}"

            await conn.execute(
                "UPDATE wallets SET balance = $1, updated_at = NOW() WHERE id = $2",
                new_balance,
                wallet["id"],
            )
            await conn.execute(
                """
                INSERT INTO wallet_transactions
                    (wallet_id, user_id, type, amount, balance_after, reference_type, reference_id, status, description)
                VALUES ($1, $2, 'debit', $3, $4, 'invoice_payment', $5, 'completed', 'Invoice payment from wallet')
                """,
                wallet["id"],
                current_user["id"],
                amount,
                new_balance,
                invoice_id,
            )
            payment_row = await conn.fetchrow(
                """
                INSERT INTO payments (invoice_id, user_id, amount, payment_method, transaction_id, status, payment_date, updated_at)
                VALUES ($1, $2, $3, 'wallet', $4, 'completed', NOW(), NOW())
                RETURNING *
                """,
                invoice_id,
                current_user["id"],
                amount,
                transaction_id,
            )
            await conn.execute(
                "UPDATE invoices SET status = 'paid', paid_at = NOW(), updated_at = NOW() WHERE id = $1",
                invoice_id,
            )

        return {"payment": dict(payment_row), "wallet_balance": new_balance, "message": "Payment successful"}


@router.post("/invoices/{invoice_id}/order")
async def create_invoice_payment_order(invoice_id: int, current_user: dict = Depends(get_current_user)):
    """Create a PhonePe payment and return the hosted checkout redirect URL."""
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

        merchant_transaction_id = new_merchant_transaction_id(f"INV{invoice_id}")

        if _allow_direct_credit_fallback():
            order_row = await conn.fetchrow(
                """
                INSERT INTO payment_orders (user_id, invoice_id, purpose, amount, currency, gateway, gateway_order_id, status)
                VALUES ($1, $2, 'invoice_payment', $3, 'INR', 'manual', $4, 'created')
                RETURNING *
                """,
                current_user["id"],
                invoice_id,
                invoice["total_amount"],
                merchant_transaction_id,
            )
            payment_row = await _finalize_invoice_payment(conn, dict(order_row))
            return {
                "order": {**dict(order_row), "status": "completed"},
                "merchant_transaction_id": merchant_transaction_id,
                "redirect_url": None,
                "payment": payment_row,
                "message": "Invoice paid directly (PhonePe not configured; dev mode)",
            }

        try:
            result = await create_phonepe_payment(
                amount_rupees=float(invoice["total_amount"]),
                merchant_transaction_id=merchant_transaction_id,
                user_id=current_user["id"],
                notes={"purpose": "invoice_payment", "invoice_id": str(invoice_id)},
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

        redirect_url = (
            result.get("data", {}).get("instrumentResponse", {}).get("redirectInfo", {}).get("url")
        )

        order_row = await conn.fetchrow(
            """
            INSERT INTO payment_orders (user_id, invoice_id, purpose, amount, currency, gateway, gateway_order_id, status)
            VALUES ($1, $2, 'invoice_payment', $3, 'INR', 'phonepe', $4, 'created')
            RETURNING *
            """,
            current_user["id"],
            invoice_id,
            invoice["total_amount"],
            merchant_transaction_id,
        )

        return {
            "order": dict(order_row),
            "merchant_transaction_id": merchant_transaction_id,
            "redirect_url": redirect_url,
        }


async def _finalize_invoice_payment(conn, order: dict) -> Optional[dict]:
    """Mark an invoice payment order + invoice as paid. Returns the payment row, or None if already done."""
    if order["status"] == "completed":
        return None
    async with conn.transaction():
        transaction_id = f"TXN_{int(datetime.utcnow().timestamp())}_{secrets.token_hex(4)}"
        payment_row = await conn.fetchrow(
            """
            INSERT INTO payments (invoice_id, user_id, amount, payment_method, transaction_id, status, payment_date, updated_at)
            VALUES ($1, $2, $3, 'phonepe', $4, 'completed', NOW(), NOW())
            RETURNING *
            """,
            order["invoice_id"],
            order["user_id"],
            order["amount"],
            transaction_id,
        )
        await conn.execute(
            "UPDATE invoices SET status = 'paid', paid_at = NOW(), updated_at = NOW() WHERE id = $1",
            order["invoice_id"],
        )
        await conn.execute(
            "UPDATE payment_orders SET status = 'completed', updated_at = NOW() WHERE id = $1",
            order["id"],
        )
    return dict(payment_row)


@router.get("/invoices/{invoice_id}/status")
async def get_invoice_payment_status(invoice_id: int, current_user: dict = Depends(get_current_user)):
    """Poll PhonePe for the latest status of the most recent order and finalize if paid."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        order_row = await conn.fetchrow(
            """
            SELECT * FROM payment_orders
            WHERE invoice_id = $1 AND user_id = $2 AND purpose = 'invoice_payment'
            ORDER BY created_at DESC LIMIT 1
            """,
            invoice_id,
            current_user["id"],
        )
        if not order_row:
            raise HTTPException(status_code=404, detail="Order not found")

        order = dict(order_row)
        if order["status"] != "completed":
            status_data = await check_phonepe_status(order["gateway_order_id"])
            code = status_data.get("code", "")
            if code == "PAYMENT_SUCCESS":
                await _finalize_invoice_payment(conn, order)
                order["status"] = "completed"
            elif code in ("PAYMENT_ERROR", "PAYMENT_DECLINED"):
                await conn.execute(
                    "UPDATE payment_orders SET status = 'failed', updated_at = NOW() WHERE id = $1",
                    order["id"],
                )
                order["status"] = "failed"

        return {"status": order["status"], "invoice_id": invoice_id}


@router.get("/wallet")
async def get_wallet(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await _get_or_create_wallet(conn, current_user["id"])


@router.get("/wallet/transactions")
async def list_wallet_transactions(current_user: dict = Depends(get_current_user)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        wallet = await _get_or_create_wallet(conn, current_user["id"])
        rows = await conn.fetch(
            "SELECT * FROM wallet_transactions WHERE wallet_id = $1 ORDER BY created_at DESC",
            wallet["id"],
        )
        return [dict(r) for r in rows]


@router.post("/wallet/topup/order")
async def create_wallet_topup_order(
    request: WalletTopupRequest, current_user: dict = Depends(get_current_user)
):
    """Create a PhonePe payment to add money to the user's wallet."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        wallet = await _get_or_create_wallet(conn, current_user["id"])
        merchant_transaction_id = new_merchant_transaction_id(f"WAL{wallet['id']}")

        if _allow_direct_credit_fallback():
            order_row = await conn.fetchrow(
                """
                INSERT INTO payment_orders (user_id, purpose, amount, currency, gateway, gateway_order_id, status)
                VALUES ($1, 'wallet_topup', $2, 'INR', 'manual', $3, 'created')
                RETURNING *
                """,
                current_user["id"],
                request.amount,
                merchant_transaction_id,
            )
            tx_row = await _finalize_wallet_topup(conn, dict(order_row))
            new_wallet = await conn.fetchrow("SELECT * FROM wallets WHERE id = $1", wallet["id"])
            return {
                "order": {**dict(order_row), "status": "completed"},
                "merchant_transaction_id": merchant_transaction_id,
                "redirect_url": None,
                "wallet_transaction": tx_row,
                "balance": float(new_wallet["balance"]),
                "message": "Wallet topped up directly (PhonePe not configured; dev mode)",
            }

        try:
            result = await create_phonepe_payment(
                amount_rupees=request.amount,
                merchant_transaction_id=merchant_transaction_id,
                user_id=current_user["id"],
                notes={"purpose": "wallet_topup", "user_id": str(current_user["id"])},
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))

        redirect_url = (
            result.get("data", {}).get("instrumentResponse", {}).get("redirectInfo", {}).get("url")
        )

        order_row = await conn.fetchrow(
            """
            INSERT INTO payment_orders (user_id, purpose, amount, currency, gateway, gateway_order_id, status)
            VALUES ($1, 'wallet_topup', $2, 'INR', 'phonepe', $3, 'created')
            RETURNING *
            """,
            current_user["id"],
            request.amount,
            merchant_transaction_id,
        )

        return {
            "order": dict(order_row),
            "merchant_transaction_id": merchant_transaction_id,
            "redirect_url": redirect_url,
        }


async def _finalize_wallet_topup(conn, order: dict) -> Optional[dict]:
    """Credit the wallet for a completed top-up order. Returns the transaction row, or None if already done."""
    if order["status"] == "completed":
        return None
    async with conn.transaction():
        wallet = await _get_or_create_wallet(conn, order["user_id"])
        new_balance = float(wallet["balance"]) + float(order["amount"])

        await conn.execute(
            "UPDATE wallets SET balance = $1, updated_at = NOW() WHERE id = $2",
            new_balance,
            wallet["id"],
        )
        tx_row = await conn.fetchrow(
            """
            INSERT INTO wallet_transactions
                (wallet_id, user_id, type, amount, balance_after, reference_type, reference_id, gateway_order_id, status, description)
            VALUES ($1, $2, 'credit', $3, $4, 'topup', $5, $6, 'completed', 'Wallet top-up via PhonePe')
            RETURNING *
            """,
            wallet["id"],
            order["user_id"],
            order["amount"],
            new_balance,
            order["id"],
            order["gateway_order_id"],
        )
        await conn.execute(
            "UPDATE payment_orders SET status = 'completed', updated_at = NOW() WHERE id = $1",
            order["id"],
        )
    return dict(tx_row)


@router.get("/wallet/topup/status")
async def get_wallet_topup_status(
    merchant_transaction_id: str, current_user: dict = Depends(get_current_user)
):
    """Poll PhonePe for the latest status of a wallet top-up order and finalize if paid."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        order_row = await conn.fetchrow(
            "SELECT * FROM payment_orders WHERE gateway_order_id = $1 AND user_id = $2 AND purpose = 'wallet_topup'",
            merchant_transaction_id,
            current_user["id"],
        )
        if not order_row:
            raise HTTPException(status_code=404, detail="Order not found")

        order = dict(order_row)
        if order["status"] != "completed":
            status_data = await check_phonepe_status(order["gateway_order_id"])
            code = status_data.get("code", "")
            if code == "PAYMENT_SUCCESS":
                await _finalize_wallet_topup(conn, order)
                order["status"] = "completed"
            elif code in ("PAYMENT_ERROR", "PAYMENT_DECLINED"):
                await conn.execute(
                    "UPDATE payment_orders SET status = 'failed', updated_at = NOW() WHERE id = $1",
                    order["id"],
                )
                order["status"] = "failed"

        return {"status": order["status"]}


@router.post("/webhook/phonepe")
async def phonepe_webhook(request: Request):
    """PhonePe server-to-server callback for reconciling payment status asynchronously."""
    body = await request.body()
    signature = request.headers.get("X-VERIFY", "")
    if not verify_callback_signature(body, signature):
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    payload = decode_callback_payload(body)
    merchant_transaction_id = payload.get("data", {}).get("merchantTransactionId", "")
    code = payload.get("code", "")

    pool = await get_pool()
    async with pool.acquire() as conn:
        order_row = await conn.fetchrow(
            "SELECT * FROM payment_orders WHERE gateway_order_id = $1", merchant_transaction_id
        )
        if order_row:
            order = dict(order_row)
            if code == "PAYMENT_SUCCESS":
                if order["purpose"] == "invoice_payment":
                    await _finalize_invoice_payment(conn, order)
                elif order["purpose"] == "wallet_topup":
                    await _finalize_wallet_topup(conn, order)
            elif code in ("PAYMENT_ERROR", "PAYMENT_DECLINED"):
                await conn.execute(
                    "UPDATE payment_orders SET status = 'failed', updated_at = NOW() WHERE id = $1",
                    order["id"],
                )

    return {"status": "ok"}


@router.get("/callback/phonepe")
async def phonepe_redirect_callback(merchantTransactionId: str = ""):
    """Browser redirect target after the user completes/cancels PhonePe checkout."""
    frontend_url = os.getenv("PHONEPE_APP_REDIRECT_URL", "/")
    if not merchantTransactionId:
        return RedirectResponse(url=f"{frontend_url}?status=unknown")

    pool = await get_pool()
    async with pool.acquire() as conn:
        order_row = await conn.fetchrow(
            "SELECT * FROM payment_orders WHERE gateway_order_id = $1", merchantTransactionId
        )
        if not order_row:
            return RedirectResponse(url=f"{frontend_url}?status=unknown")

        order = dict(order_row)
        if order["status"] != "completed":
            status_data = await check_phonepe_status(merchantTransactionId)
            code = status_data.get("code", "")
            if code == "PAYMENT_SUCCESS":
                if order["purpose"] == "invoice_payment":
                    await _finalize_invoice_payment(conn, order)
                elif order["purpose"] == "wallet_topup":
                    await _finalize_wallet_topup(conn, order)
                order["status"] = "completed"
            elif code in ("PAYMENT_ERROR", "PAYMENT_DECLINED"):
                await conn.execute(
                    "UPDATE payment_orders SET status = 'failed', updated_at = NOW() WHERE id = $1",
                    order["id"],
                )
                order["status"] = "failed"

    return RedirectResponse(url=f"{frontend_url}?status={order['status']}&merchantTransactionId={merchantTransactionId}")


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

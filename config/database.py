import os
import asyncpg
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:root123@localhost:5432/evcharge",
)

# Global connection pool
pool: asyncpg.pool.Pool | None = None


async def get_pool() -> asyncpg.pool.Pool:
    """Return the global asyncpg pool (creates it on first call)."""
    global pool
    if pool is None:
        pool = await asyncpg.create_pool(
            dsn=DATABASE_URL,
            min_size=int(os.getenv("PG_POOL_MIN", "1")),
            max_size=int(os.getenv("PG_POOL_MAX", "10")),
            command_timeout=int(os.getenv("PG_COMMAND_TIMEOUT", "60")),
        )
    return pool


async def drop_all_tables(conn):
    """Drop all tables in cascade order."""
    try:
        await conn.execute(
            """
            DROP TABLE IF EXISTS home_banners CASCADE;
            DROP TABLE IF EXISTS tariffs CASCADE;
            DROP TABLE IF EXISTS fleet_invoices CASCADE;
            DROP TABLE IF EXISTS payment_orders CASCADE;
            DROP TABLE IF EXISTS wallet_transactions CASCADE;
            DROP TABLE IF EXISTS wallets CASCADE;
            DROP TABLE IF EXISTS payments CASCADE;
            DROP TABLE IF EXISTS invoices CASCADE;
            DROP TABLE IF EXISTS vehicle_usage_log CASCADE;
            DROP TABLE IF EXISTS sessions CASCADE;
            DROP TABLE IF EXISTS bookings CASCADE;
            DROP TABLE IF EXISTS charging_guns CASCADE;
            DROP TABLE IF EXISTS connectors CASCADE;
            DROP TABLE IF EXISTS stations CASCADE;
            DROP TABLE IF EXISTS vehicle_maintenance CASCADE;
            DROP TABLE IF EXISTS fleet_tariffs CASCADE;
            DROP TABLE IF EXISTS fleet_vehicles CASCADE;
            DROP TABLE IF EXISTS fleet_members CASCADE;
            DROP TABLE IF EXISTS vehicles CASCADE;
            DROP TABLE IF EXISTS fleets CASCADE;
            DROP TABLE IF EXISTS refresh_tokens CASCADE;
            DROP TABLE IF EXISTS users CASCADE;
            """
        )
        logger.info("All tables dropped successfully")
    except Exception as e:
        logger.warning(f"Error dropping tables: {e}")


async def _migrate_legacy_wallet_schema(conn) -> None:
    """Rename out pre-existing wallet tables that predate the id/wallet_id columns.

    Older deployments created `wallets`/`wallet_transactions` with a different shape
    (no surrogate `id`/`wallet_id`). Renaming them lets ensure_wallet_tables create the
    current schema fresh, then any usable data is copied back in below.
    """
    wallets_ok = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'wallets' AND column_name = 'id'"
    )
    if await conn.fetchval("SELECT to_regclass('public.wallets')") is not None and not wallets_ok:
        await conn.execute("ALTER TABLE wallets RENAME TO wallets_legacy")

    wt_ok = await conn.fetchval(
        "SELECT 1 FROM information_schema.columns WHERE table_name = 'wallet_transactions' AND column_name = 'wallet_id'"
    )
    if await conn.fetchval("SELECT to_regclass('public.wallet_transactions')") is not None and not wt_ok:
        await conn.execute("ALTER TABLE wallet_transactions RENAME TO wallet_transactions_legacy")


async def ensure_wallet_tables(conn) -> None:
    """Create wallet/payment-gateway tables if they do not exist yet (idempotent)."""
    await _migrate_legacy_wallet_schema(conn)
    await conn.execute(
        """
        CREATE TABLE IF NOT EXISTS wallets (
            id SERIAL PRIMARY KEY,
            user_id INTEGER UNIQUE NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            balance DECIMAL(10,2) NOT NULL DEFAULT 0,
            currency VARCHAR(10) NOT NULL DEFAULT 'INR',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS wallet_transactions (
            id SERIAL PRIMARY KEY,
            wallet_id INTEGER NOT NULL REFERENCES wallets(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            type VARCHAR(20) NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            balance_after DECIMAL(10,2) NOT NULL,
            reference_type VARCHAR(50),
            reference_id INTEGER,
            gateway_order_id VARCHAR(255),
            gateway_payment_id VARCHAR(255),
            status VARCHAR(30) NOT NULL DEFAULT 'completed',
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS payment_orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            invoice_id INTEGER REFERENCES invoices(id) ON DELETE SET NULL,
            purpose VARCHAR(30) NOT NULL,
            amount DECIMAL(10,2) NOT NULL,
            currency VARCHAR(10) NOT NULL DEFAULT 'INR',
            gateway VARCHAR(30) NOT NULL DEFAULT 'phonepe',
            gateway_order_id VARCHAR(255) UNIQUE,
            gateway_payment_id VARCHAR(255),
            status VARCHAR(30) NOT NULL DEFAULT 'created',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_wallets_user_id ON wallets(user_id);
        CREATE INDEX IF NOT EXISTS idx_wallet_transactions_wallet_id ON wallet_transactions(wallet_id);
        CREATE INDEX IF NOT EXISTS idx_wallet_transactions_user_id ON wallet_transactions(user_id);
        CREATE INDEX IF NOT EXISTS idx_payment_orders_user_id ON payment_orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_payment_orders_invoice_id ON payment_orders(invoice_id);
        CREATE INDEX IF NOT EXISTS idx_payment_orders_gateway_order_id ON payment_orders(gateway_order_id);
        """
    )
    # Carry over balances from a renamed legacy wallets table, then drop it.
    if await conn.fetchval("SELECT to_regclass('public.wallets_legacy')") is not None:
        await conn.execute(
            """
            INSERT INTO wallets (user_id, balance, currency, created_at, updated_at)
            SELECT user_id, balance, currency, created_at, updated_at FROM wallets_legacy
            ON CONFLICT (user_id) DO NOTHING
            """
        )
        await conn.execute("DROP TABLE wallets_legacy")

    if await conn.fetchval("SELECT to_regclass('public.wallet_transactions_legacy')") is not None:
        await conn.execute("DROP TABLE wallet_transactions_legacy")

    # Backfill wallets for any users created before wallets existed.
    await conn.execute(
        """
        INSERT INTO wallets (user_id)
        SELECT u.id FROM users u
        LEFT JOIN wallets w ON w.user_id = u.id
        WHERE w.id IS NULL
        """
    )


async def ensure_wallet(conn, user_id: int) -> dict:
    """Return the user's wallet, creating it if it does not exist yet."""
    wallet = await conn.fetchrow("SELECT * FROM wallets WHERE user_id = $1", user_id)
    if wallet:
        return dict(wallet)
    wallet = await conn.fetchrow(
        """
        INSERT INTO wallets (user_id) VALUES ($1)
        ON CONFLICT (user_id) DO UPDATE SET user_id = EXCLUDED.user_id
        RETURNING *
        """,
        user_id,
    )
    return dict(wallet)


async def get_account_type(conn, user_id: int) -> str:
    """'fleet_owner' if the user owns/administers any fleet, otherwise 'driver'.

    Used by the frontend to route a logged-in user to the right home screen.
    """
    is_fleet_admin = await conn.fetchval(
        """
        SELECT 1 FROM fleets WHERE owner_id = $1
        UNION
        SELECT 1 FROM fleet_members WHERE user_id = $1 AND role = 'admin'
        LIMIT 1
        """,
        user_id,
    )
    return "fleet_owner" if is_fleet_admin else "driver"


async def get_fleet_memberships(conn, user_id: int) -> list:
    """All fleets/roles this user belongs to (empty for a plain driver)."""
    rows = await conn.fetch(
        """
        SELECT f.id as fleet_id, f.name as fleet_name, fm.role
        FROM fleets f
        JOIN fleet_members fm ON fm.fleet_id = f.id
        WHERE fm.user_id = $1
        ORDER BY f.created_at DESC
        """,
        user_id,
    )
    return [dict(r) for r in rows]


async def get_role_summary(conn, user_id: int, base_role: str = "driver") -> dict:
    """Everything the frontend needs to route a logged-in user: system role, fleet
    memberships (each with its own role), and the derived account_type."""
    fleet_memberships = await get_fleet_memberships(conn, user_id)
    account_type = "fleet_owner" if any(m["role"] == "admin" for m in fleet_memberships) else "driver"
    roles = sorted({base_role} | {m["role"] for m in fleet_memberships})
    return {
        "role": base_role,
        "account_type": account_type,
        "roles": roles,
        "fleet_memberships": fleet_memberships,
    }


async def init_database() -> None:
    """Initialize schema. Data reset only when explicitly enabled."""
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        reset_on_startup = os.getenv("RESET_DB_ON_STARTUP", "false").strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )

        # If schema already exists, keep data and skip destructive re-init.
        users_table_exists = await conn.fetchval("SELECT to_regclass('public.users')") is not None
        if users_table_exists and not reset_on_startup:
            # Still add any new tables introduced after the initial deployment.
            await ensure_wallet_tables(conn)
            logger.info("Database schema already exists; skipping destructive initialization")
            return

        # Explicit reset path for local/dev re-seeding.
        if reset_on_startup:
            await drop_all_tables(conn)

        # Create all tables fresh
        await conn.execute(
            """
            CREATE TABLE users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                phone VARCHAR(50),
                role VARCHAR(50) DEFAULT 'driver',
                auth_provider VARCHAR(30) DEFAULT 'email',
                google_sub VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE refresh_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                token_hash VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE fleets (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT,
                owner_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                billing_contact_name VARCHAR(255),
                billing_contact_email VARCHAR(255),
                billing_contact_phone VARCHAR(50),
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE vehicles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                make VARCHAR(100),
                model VARCHAR(100),
                year INTEGER,
                battery_capacity_kwh DECIMAL(10,2),
                connector_type VARCHAR(50),
                license_plate VARCHAR(50),
                is_default BOOLEAN DEFAULT false,
                status VARCHAR(50) DEFAULT 'active',
                vehicle_type VARCHAR(50) DEFAULT 'personal',
                vin VARCHAR(100),
                odometer_reading INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE fleet_members (
                id SERIAL PRIMARY KEY,
                fleet_id INTEGER NOT NULL REFERENCES fleets(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                role VARCHAR(50) NOT NULL DEFAULT 'driver',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(fleet_id, user_id)
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE fleet_vehicles (
                id SERIAL PRIMARY KEY,
                fleet_id INTEGER NOT NULL REFERENCES fleets(id) ON DELETE CASCADE,
                vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
                assigned_to_user_id INTEGER REFERENCES users(id),
                is_shared BOOLEAN DEFAULT false,
                status VARCHAR(50) DEFAULT 'active',
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(fleet_id, vehicle_id)
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE fleet_tariffs (
                id SERIAL PRIMARY KEY,
                fleet_id INTEGER NOT NULL REFERENCES fleets(id) ON DELETE CASCADE,
                connector_type VARCHAR(50),
                power_type VARCHAR(20),
                price_per_kwh DECIMAL(10,4),
                price_per_minute DECIMAL(10,4),
                status VARCHAR(50) DEFAULT 'active',
                valid_from TIMESTAMP,
                valid_to TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE vehicle_maintenance (
                id SERIAL PRIMARY KEY,
                vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
                fleet_id INTEGER REFERENCES fleets(id) ON DELETE CASCADE,
                maintenance_type VARCHAR(100),
                description TEXT,
                performed_by VARCHAR(255),
                performed_date TIMESTAMP,
                next_due_date DATE,
                cost DECIMAL(10,2),
                status VARCHAR(50) DEFAULT 'completed',
                notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE stations (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                address TEXT,
                latitude DECIMAL(10,8),
                longitude DECIMAL(11,8),
                operator_name VARCHAR(255),
                amenities TEXT[],
                status VARCHAR(50) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE connectors (
                id SERIAL PRIMARY KEY,
                station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
                name VARCHAR(100),
                connector_type VARCHAR(50),
                power_type VARCHAR(20),
                max_power_kw DECIMAL(10,2),
                price_per_kwh DECIMAL(10,4),
                price_per_minute DECIMAL(10,4),
                status VARCHAR(50) DEFAULT 'available',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE charging_guns (
                id SERIAL PRIMARY KEY,
                connector_id INTEGER NOT NULL REFERENCES connectors(id) ON DELETE CASCADE,
                gun_number INTEGER NOT NULL,
                gun_name VARCHAR(100),
                qr_code VARCHAR(255) UNIQUE NOT NULL,
                barcode_code VARCHAR(255) UNIQUE NOT NULL,
                status VARCHAR(50) DEFAULT 'available',
                last_used_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(connector_id, gun_number)
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE bookings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                fleet_id INTEGER REFERENCES fleets(id) ON DELETE SET NULL,
                vehicle_id INTEGER REFERENCES vehicles(id),
                station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
                connector_id INTEGER REFERENCES connectors(id),
                charging_gun_id INTEGER REFERENCES charging_guns(id),
                status VARCHAR(50) DEFAULT 'pending',
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                pricing_snapshot JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                fleet_id INTEGER REFERENCES fleets(id) ON DELETE SET NULL,
                vehicle_id INTEGER REFERENCES vehicles(id),
                station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
                connector_id INTEGER REFERENCES connectors(id),
                charging_gun_id INTEGER REFERENCES charging_guns(id),
                booking_id INTEGER REFERENCES bookings(id),
                status VARCHAR(50) DEFAULT 'active',
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                energy_kwh DECIMAL(10,3),
                cost DECIMAL(10,2),
                tariff_snapshot JSONB,
                energy_source VARCHAR(30) DEFAULT 'client',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE vehicle_usage_log (
                id SERIAL PRIMARY KEY,
                vehicle_id INTEGER NOT NULL REFERENCES vehicles(id) ON DELETE CASCADE,
                fleet_id INTEGER REFERENCES fleets(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id),
                session_id INTEGER REFERENCES sessions(id),
                charging_gun_id INTEGER REFERENCES charging_guns(id),
                distance_km DECIMAL(8,2),
                energy_consumed_kwh DECIMAL(8,3),
                start_odometer INTEGER,
                end_odometer INTEGER,
                cost DECIMAL(10,2),
                usage_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE invoices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                fleet_id INTEGER REFERENCES fleets(id) ON DELETE CASCADE,
                session_id INTEGER REFERENCES sessions(id),
                amount DECIMAL(10,2),
                tax_amount DECIMAL(10,2),
                total_amount DECIMAL(10,2),
                status VARCHAR(50) DEFAULT 'pending',
                due_date DATE,
                paid_at TIMESTAMP,
                invoice_number VARCHAR(100) UNIQUE,
                billing_period_start DATE,
                billing_period_end DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE payments (
                id SERIAL PRIMARY KEY,
                invoice_id INTEGER REFERENCES invoices(id),
                user_id INTEGER REFERENCES users(id),
                fleet_id INTEGER REFERENCES fleets(id) ON DELETE CASCADE,
                amount DECIMAL(10,2),
                payment_method VARCHAR(50),
                transaction_id VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                paid_amount DECIMAL(10,2),
                payment_date TIMESTAMP,
                reference_number VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE fleet_invoices (
                id SERIAL PRIMARY KEY,
                fleet_id INTEGER NOT NULL REFERENCES fleets(id) ON DELETE CASCADE,
                billing_period_start DATE NOT NULL,
                billing_period_end DATE NOT NULL,
                total_sessions INTEGER,
                total_energy_kwh DECIMAL(10,3),
                amount DECIMAL(10,2),
                tax_amount DECIMAL(10,2),
                total_amount DECIMAL(10,2),
                status VARCHAR(50) DEFAULT 'pending',
                due_date DATE,
                paid_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE tariffs (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255),
                connector_type VARCHAR(50),
                power_type VARCHAR(20),
                price_per_kwh DECIMAL(10,4),
                price_per_minute DECIMAL(10,4),
                currency VARCHAR(10) DEFAULT 'INR',
                valid_from TIMESTAMP,
                valid_to TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await conn.execute(
            """
            CREATE TABLE home_banners (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                subtitle TEXT,
                image_url TEXT NOT NULL,
                cta_text TEXT,
                cta_action TEXT,
                priority INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT true,
                start_at TIMESTAMP,
                end_at TIMESTAMP,
                target_role VARCHAR(50) DEFAULT 'all',
                target_city TEXT,
                target_state TEXT,
                min_app_version TEXT,
                max_app_version TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        await ensure_wallet_tables(conn)

        # Create indexes for performance
        await conn.execute(
            """
            CREATE INDEX idx_connectors_station ON connectors(station_id);
            CREATE INDEX idx_connectors_status ON connectors(status);
            CREATE INDEX idx_charging_guns_connector ON charging_guns(connector_id);
            CREATE INDEX idx_charging_guns_qr ON charging_guns(qr_code);
            CREATE INDEX idx_charging_guns_barcode ON charging_guns(barcode_code);
            CREATE INDEX idx_bookings_connector_time ON bookings(connector_id, start_time, end_time);
            CREATE INDEX idx_bookings_fleet_id ON bookings(fleet_id);
            CREATE INDEX idx_bookings_user_id ON bookings(user_id);
            CREATE INDEX idx_bookings_gun_id ON bookings(charging_gun_id);
            CREATE INDEX idx_sessions_connector_status ON sessions(connector_id, status);
            CREATE INDEX idx_sessions_fleet_id ON sessions(fleet_id);
            CREATE INDEX idx_sessions_user_id ON sessions(user_id);
            CREATE INDEX idx_sessions_gun_id ON sessions(charging_gun_id);
            CREATE INDEX idx_stations_lat_lng ON stations(latitude, longitude);
            CREATE INDEX idx_fleet_members_fleet_id ON fleet_members(fleet_id);
            CREATE INDEX idx_fleet_members_user_id ON fleet_members(user_id);
            CREATE INDEX idx_fleet_vehicles_fleet_id ON fleet_vehicles(fleet_id);
            CREATE INDEX idx_fleets_owner_id ON fleets(owner_id);
            CREATE INDEX idx_invoices_user_id ON invoices(user_id);
            CREATE INDEX idx_invoices_fleet_id ON invoices(fleet_id);
            CREATE INDEX idx_invoices_status ON invoices(status);
            CREATE INDEX idx_payments_fleet_id ON payments(fleet_id);
            CREATE INDEX idx_payments_user_id ON payments(user_id);
            CREATE INDEX idx_vehicles_user_id ON vehicles(user_id);
            CREATE INDEX idx_vehicles_status ON vehicles(status);
            """
        )

        # Seed data
        await seed_data(conn)
        logger.info("Database initialized successfully")


async def seed_data(conn: asyncpg.Connection) -> None:
    """Seed initial data into database."""
    # Insert stations
    await conn.execute(
        """
        INSERT INTO stations (name, address, latitude, longitude, operator_name, amenities, status) VALUES
        ('Jangareddy Gudem EV Hub', 'Main Road, Near Bus Stand, Jangareddy Gudem, West Godavari, Andhra Pradesh', 17.1200, 81.3000, 'ChargePoint', ARRAY['WiFi', 'Restroom', 'Coffee', 'Parking', 'Accessibility'], 'active'),
        ('Vizag Beach Charging Station', 'Beach Road, Opposite Kali Temple, Visakhapatnam, Andhra Pradesh', 17.7266, 83.3068, 'Tesla', ARRAY['Shopping', 'Food Court', 'Parking', 'Sea View'], 'active'),
        ('Vizag Airport Quick Charge', 'Airport Road, Near Vizag International Airport, Visakhapatnam, Andhra Pradesh', 17.7210, 83.2247, 'Electrify America', ARRAY['Restroom', 'Vending', 'Parking', 'Security'], 'active'),
        ('Hyderabad Fast Charge', 'Gachibowli, Near Outer Ring Road, Hyderabad, Telangana', 17.4401, 78.3489, 'EVgo', ARRAY['Restroom', 'Food', 'Gas', 'Parking', 'Lounge'], 'active'),
        ('Hyderabad Tech Park Station', 'HITEC City, Near Cyber Towers, Hyderabad, Telangana', 17.4474, 78.3717, 'ChargePoint', ARRAY['WiFi', 'Security', 'Parking', 'Cafe'], 'active'),
        ('Bengaluru Highway Charge', 'Electronic City, Near NICE Road, Bengaluru, Karnataka', 12.8456, 77.6603, 'Ather Grid', ARRAY['WiFi', 'Restroom', 'Parking', 'Cafe'], 'active'),
        ('Chennai Metro Charge', 'Anna Nagar, Near 100 Feet Road, Chennai, Tamil Nadu', 13.0848, 80.2093, 'ChargePoint', ARRAY['Restroom', 'Parking', 'Security', 'Shopping'], 'active'),
        ('Pune IT Park Station', 'Hinjawadi, Near Phase 2, Pune, Maharashtra', 18.5972, 73.7167, 'EVgo', ARRAY['WiFi', 'Coffee', 'Parking', 'Accessibility'], 'active'),
        ('Kolkata Downtown Charge', 'Salt Lake, Near Sector V, Kolkata, West Bengal', 22.5769, 88.4332, 'Tesla', ARRAY['Restroom', 'Parking', 'Food Court', 'Security'], 'active'),
        ('Jaipur City Station', 'Malviya Nagar, Near 200 Feet Road, Jaipur, Rajasthan', 26.8500, 75.8000, 'Electrify America', ARRAY['WiFi', 'Cafe', 'Parking', 'Restroom'], 'active');
        """
    )

    # Insert connectors
    await conn.execute(
        """
        INSERT INTO connectors (station_id, name, connector_type, power_type, max_power_kw, price_per_kwh, price_per_minute, status) VALUES
        (1, 'DC Fast 1', 'CCS2', 'DC', 150, 0.35, 0.00, 'available'),
        (1, 'DC Fast 2', 'CCS2', 'DC', 150, 0.35, 0.00, 'available'),
        (1, 'AC Type2 1', 'TYPE2', 'AC', 22, 0.25, 0.00, 'available'),
        (2, 'Tesla SC 1', 'TESLA', 'DC', 250, 0.28, 0.00, 'available'),
        (2, 'Tesla SC 2', 'TESLA', 'DC', 250, 0.28, 0.00, 'available'),
        (3, 'Ultra Fast 1', 'CCS2', 'DC', 350, 0.40, 0.00, 'available'),
        (3, 'Ultra Fast 2', 'CCS2', 'DC', 350, 0.40, 0.00, 'available'),
        (4, 'Highway DC 1', 'CCS2', 'DC', 150, 0.38, 0.00, 'available'),
        (4, 'Highway AC 1', 'TYPE2', 'AC', 11, 0.20, 0.00, 'available'),
        (5, 'Office AC 1', 'TYPE2', 'AC', 22, 0.22, 0.00, 'available'),
        (5, 'Office AC 2', 'TYPE2', 'AC', 22, 0.22, 0.00, 'available');
        """
    )

    # Insert charging guns (multiple guns per connector)
    await conn.execute(
        """
        INSERT INTO charging_guns (connector_id, gun_number, gun_name, qr_code, barcode_code, status) VALUES
        (1, 1, 'Gun A', 'QR-JGD-1-1', 'BC-JGD-1-1', 'available'),
        (1, 2, 'Gun B', 'QR-JGD-1-2', 'BC-JGD-1-2', 'available'),
        (2, 1, 'Gun A', 'QR-JGD-2-1', 'BC-JGD-2-1', 'available'),
        (2, 2, 'Gun B', 'QR-JGD-2-2', 'BC-JGD-2-2', 'available'),
        (3, 1, 'Gun A', 'QR-JGD-3-1', 'BC-JGD-3-1', 'available'),
        (4, 1, 'Gun A', 'QR-VIZ-4-1', 'BC-VIZ-4-1', 'available'),
        (4, 2, 'Gun B', 'QR-VIZ-4-2', 'BC-VIZ-4-2', 'available'),
        (5, 1, 'Gun A', 'QR-VIZ-5-1', 'BC-VIZ-5-1', 'available'),
        (5, 2, 'Gun B', 'QR-VIZ-5-2', 'BC-VIZ-5-2', 'available'),
        (6, 1, 'Gun A', 'QR-VIZ-6-1', 'BC-VIZ-6-1', 'available'),
        (6, 2, 'Gun B', 'QR-VIZ-6-2', 'BC-VIZ-6-2', 'available'),
        (7, 1, 'Gun A', 'QR-HYD-7-1', 'BC-HYD-7-1', 'available'),
        (7, 2, 'Gun B', 'QR-HYD-7-2', 'BC-HYD-7-2', 'available'),
        (8, 1, 'Gun A', 'QR-HYD-8-1', 'BC-HYD-8-1', 'available'),
        (9, 1, 'Gun A', 'QR-HYD-9-1', 'BC-HYD-9-1', 'available'),
        (10, 1, 'Gun A', 'QR-BNG-10-1', 'BC-BNG-10-1', 'available'),
        (10, 2, 'Gun B', 'QR-BNG-10-2', 'BC-BNG-10-2', 'available'),
        (11, 1, 'Gun A', 'QR-CHN-11-1', 'BC-CHN-11-1', 'available');
        """
    )

    # Insert tariffs
    await conn.execute(
        """
        INSERT INTO tariffs (name, connector_type, power_type, price_per_kwh, price_per_minute, currency) VALUES
        ('Standard AC', 'TYPE2', 'AC', 0.22, 0.00, 'USD'),
        ('Fast DC', 'CCS2', 'DC', 0.35, 0.00, 'USD'),
        ('Ultra Fast DC', 'CCS2', 'DC', 0.40, 0.00, 'USD'),
        ('Tesla Supercharger', 'TESLA', 'DC', 0.28, 0.00, 'USD');
        """
    )

    # Insert default banner
    await conn.execute(
        """
        INSERT INTO home_banners (title, subtitle, image_url, cta_text, cta_action, priority, is_active, target_role)
        VALUES
        ('Welcome to Charge Connect', 'Find fast chargers near you', 'https://example.com/banner.png', 'Find Chargers', 'app://stations', 10, true, 'all');
        """
    )

    logger.info("Seed data inserted successfully")


async def close_pool() -> None:
    global pool
    if pool:
        await pool.close()
        pool = None

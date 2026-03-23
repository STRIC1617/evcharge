import os
import asyncpg

import logging
logger = logging.getLogger(__name__)
logger.info("Database initialized successfully")


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


async def init_database() -> None:
    """Create tables and seed demo data."""
    db_pool = await get_pool()
    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                phone VARCHAR(50),
                role VARCHAR(50) DEFAULT 'driver',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS refresh_tokens (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                token_hash VARCHAR(255) NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                revoked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS vehicles (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                make VARCHAR(100),
                model VARCHAR(100),
                year INTEGER,
                battery_capacity_kwh DECIMAL(10,2),
                connector_type VARCHAR(50),
                license_plate VARCHAR(50),
                is_default BOOLEAN DEFAULT false,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stations (
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

            CREATE TABLE IF NOT EXISTS connectors (
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

            CREATE TABLE IF NOT EXISTS bookings (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                vehicle_id INTEGER REFERENCES vehicles(id),
                station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
                connector_id INTEGER REFERENCES connectors(id),
                status VARCHAR(50) DEFAULT 'pending',
                start_time TIMESTAMP,
                end_time TIMESTAMP,
                pricing_snapshot JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                vehicle_id INTEGER REFERENCES vehicles(id),
                station_id INTEGER NOT NULL REFERENCES stations(id) ON DELETE CASCADE,
                connector_id INTEGER REFERENCES connectors(id),
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

            CREATE TABLE IF NOT EXISTS invoices (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                session_id INTEGER REFERENCES sessions(id),
                amount DECIMAL(10,2),
                tax_amount DECIMAL(10,2),
                total_amount DECIMAL(10,2),
                status VARCHAR(50) DEFAULT 'pending',
                due_date DATE,
                paid_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS payments (
                id SERIAL PRIMARY KEY,
                invoice_id INTEGER REFERENCES invoices(id),
                user_id INTEGER REFERENCES users(id),
                amount DECIMAL(10,2),
                payment_method VARCHAR(50),
                transaction_id VARCHAR(255),
                status VARCHAR(50) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS tariffs (
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

            -- Dynamic home banners (admin-managed)
            CREATE TABLE IF NOT EXISTS home_banners (
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

            CREATE INDEX IF NOT EXISTS idx_connectors_station ON connectors(station_id);
            CREATE INDEX IF NOT EXISTS idx_connectors_status ON connectors(status);
            CREATE INDEX IF NOT EXISTS idx_bookings_connector_time ON bookings(connector_id, start_time, end_time);
            CREATE INDEX IF NOT EXISTS idx_sessions_connector_status ON sessions(connector_id, status);
            CREATE INDEX IF NOT EXISTS idx_stations_lat_lng ON stations(latitude, longitude);
            """
        )

        # Seed data if empty
        station_count = await conn.fetchval("SELECT COUNT(*) FROM stations")
        if station_count == 0:
            await seed_data(conn)

        print("Database initialized successfully")


async def seed_data(conn: asyncpg.Connection) -> None:
    await conn.execute(
        """
        INSERT INTO stations (name, address, latitude, longitude, operator_name, amenities, status) VALUES
        ('Downtown EV Hub', '123 Main St, Downtown', 40.7128, -74.0060, 'ChargePoint', ARRAY['WiFi', 'Restroom', 'Coffee'], 'active'),
        ('Mall Charging Station', '456 Shopping Blvd', 40.7580, -73.9855, 'Tesla', ARRAY['Shopping', 'Food Court'], 'active'),
        ('Airport Quick Charge', '789 Airport Rd', 40.6413, -73.7781, 'Electrify America', ARRAY['Restroom', 'Vending'], 'active'),
        ('Highway Rest Stop', '321 Interstate Dr', 40.8448, -74.0724, 'EVgo', ARRAY['Restroom', 'Food', 'Gas'], 'active'),
        ('Tech Park Station', '555 Innovation Way', 40.7484, -73.9857, 'ChargePoint', ARRAY['WiFi', 'Security'], 'active');
        """
    )

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

    await conn.execute(
        """
        INSERT INTO tariffs (name, connector_type, power_type, price_per_kwh, price_per_minute, currency) VALUES
        ('Standard AC', 'TYPE2', 'AC', 0.22, 0.00, 'USD'),
        ('Fast DC', 'CCS2', 'DC', 0.35, 0.00, 'USD'),
        ('Ultra Fast DC', 'CCS2', 'DC', 0.40, 0.00, 'USD'),
        ('Tesla Supercharger', 'TESLA', 'DC', 0.28, 0.00, 'USD');
        """
    )

    # Default banner
    await conn.execute(
        """
        INSERT INTO home_banners (title, subtitle, image_url, cta_text, cta_action, priority, is_active, target_role)
        VALUES
        ('Welcome to Charge Connect', 'Find fast chargers near you', 'https://example.com/banner.png', 'Find Chargers', 'app://stations', 10, true, 'all');
        """
    )


async def close_pool() -> None:
    global pool
    if pool:
        await pool.close()
        pool = None

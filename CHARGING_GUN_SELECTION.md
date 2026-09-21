# Charging Gun (Connector Point) Selection System

## Overview

The EV Charge API now features a comprehensive charging gun management system. Each charging station connector can have multiple guns/charging points, each with unique QR and barcode codes for easy identification and selection by users.

## Key Components

### Charging Guns Table
- **gun_number**: Sequential identifier (1, 2, 3, etc.)
- **gun_name**: Display name (Gun A, Gun B, etc.)
- **qr_code**: Unique QR code for scanning (e.g., `QR-JGD-1-1`)
- **barcode_code**: Unique barcode for scanning (e.g., `BC-JGD-1-1`)
- **status**: `available`, `in_use`, `offline`, `maintenance`
- **last_used_at**: Track usage patterns

## API Endpoints

### Get Charging Guns for a Connector
```http
GET /api/stations/{station_id}/connectors/{connector_id}/guns
Authorization: Bearer <token>
```

Response:
```json
[
  {
    "id": 1,
    "gun_number": 1,
    "gun_name": "Gun A",
    "qr_code": "QR-JGD-1-1",
    "barcode_code": "BC-JGD-1-1",
    "status": "available",
    "last_used_at": "2026-07-18T14:30:00",
    "created_at": "2026-07-18T10:00:00"
  },
  {
    "id": 2,
    "gun_number": 2,
    "gun_name": "Gun B",
    "qr_code": "QR-JGD-1-2",
    "barcode_code": "BC-JGD-1-2",
    "status": "available",
    "last_used_at": null,
    "created_at": "2026-07-18T10:00:00"
  }
]
```

### Lookup Gun by QR Code
```http
GET /api/stations/gun/qr/{qr_code}
```

**Example**: `GET /api/stations/gun/qr/QR-JGD-1-1`

Response:
```json
{
  "id": 1,
  "gun_number": 1,
  "gun_name": "Gun A",
  "qr_code": "QR-JGD-1-1",
  "barcode_code": "BC-JGD-1-1",
  "status": "available",
  "connector_id": 5,
  "connector_name": "DC Fast 1",
  "connector_type": "CCS2",
  "power_type": "DC",
  "max_power_kw": 150,
  "station_id": 1,
  "station_name": "Jangareddy Gudem EV Hub",
  "address": "Main Road, Near Bus Stand, Jangareddy Gudem, West Godavari, Andhra Pradesh",
  "latitude": 17.1200,
  "longitude": 81.3000
}
```

### Lookup Gun by Barcode
```http
GET /api/stations/gun/barcode/{barcode_code}
```

**Example**: `GET /api/stations/gun/barcode/BC-JGD-1-1`

Same response structure as QR lookup.

### List Stations with Charging Guns
```http
GET /api/stations?include_connectors=true&include_guns=true
```

Response:
```json
[
  {
    "id": 1,
    "name": "Jangareddy Gudem EV Hub",
    "address": "Main Road...",
    "latitude": 17.1200,
    "longitude": 81.3000,
    "operator_name": "ChargePoint",
    "amenities": ["WiFi", "Restroom", "Coffee", "Parking"],
    "status": "active",
    "connectors": [
      {
        "id": 1,
        "name": "DC Fast 1",
        "connector_type": "CCS2",
        "power_type": "DC",
        "max_power_kw": 150,
        "price_per_kwh": 0.35,
        "status": "available",
        "charging_guns": [
          {
            "id": 1,
            "gun_number": 1,
            "gun_name": "Gun A",
            "qr_code": "QR-JGD-1-1",
            "barcode_code": "BC-JGD-1-1",
            "status": "available"
          },
          {
            "id": 2,
            "gun_number": 2,
            "gun_name": "Gun B",
            "qr_code": "QR-JGD-1-2",
            "barcode_code": "BC-JGD-1-2",
            "status": "available"
          }
        ]
      }
    ]
  }
]
```

### Find Nearby Stations with Guns
```http
GET /api/stations/nearby?lat=17.1200&lng=81.3000&include_connectors=true&include_guns=true
```

### Create Booking with Specific Charging Gun
```http
POST /api/bookings
Content-Type: application/json
Authorization: Bearer <token>

{
  "station_id": 1,
  "connector_id": 1,
  "charging_gun_id": 1,
  "vehicle_id": 5,
  "start_time": "2026-07-20T10:00:00",
  "end_time": "2026-07-20T12:00:00"
}
```

Response:
```json
{
  "id": 15,
  "user_id": 3,
  "station_id": 1,
  "connector_id": 1,
  "charging_gun_id": 1,
  "vehicle_id": 5,
  "status": "confirmed",
  "start_time": "2026-07-20T10:00:00",
  "end_time": "2026-07-20T12:00:00",
  "pricing_snapshot": {
    "price_per_kwh": 0.35,
    "price_per_minute": 0.0,
    "max_power_kw": 150
  }
}
```

## User Workflow

### Option 1: QR Code Scanning
1. User launches app at charging station
2. App displays "Scan QR Code" button
3. User scans QR code on charging gun/connector
4. System looks up gun using `/api/stations/gun/qr/{qr_code}`
5. Gun details and station info are populated
6. User confirms and creates booking

### Option 2: Barcode Scanning
Same as QR, but uses barcode scanner:
```
GET /api/stations/gun/barcode/{barcode_code}
```

### Option 3: Manual Selection
1. User searches for station
2. Request: `GET /api/stations?include_connectors=true&include_guns=true`
3. App displays connector list with available guns
4. User selects specific gun
5. Creates booking with `charging_gun_id`

### Option 4: Nearby Stations
1. App detects user location
2. Requests: `GET /api/stations/nearby?lat={lat}&lng={lng}&include_guns=true`
3. Shows nearby stations with available guns
4. User taps gun to book

## Database Schema

```sql
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
```

## Seed Data Format

Each charging station connector has multiple guns with unique codes:

**Station**: Jangareddy Gudem EV Hub
- **Connector 1** (DC Fast 1 - CCS2, 150kW):
  - Gun 1: QR-JGD-1-1 / BC-JGD-1-1
  - Gun 2: QR-JGD-1-2 / BC-JGD-1-2

- **Connector 2** (DC Fast 2 - CCS2, 150kW):
  - Gun 1: QR-JGD-2-1 / BC-JGD-2-1
  - Gun 2: QR-JGD-2-2 / BC-JGD-2-2

- **Connector 3** (AC Type2 - Type2, 22kW):
  - Gun 1: QR-JGD-3-1 / BC-JGD-3-1

## Use Cases

### Fleet Management
Fleets can track which charging guns their vehicles use:
- Generate reports: "Vehicle X used Gun A, B, C in Q3"
- Monitor gun usage: "Gun A is heavily used, may need maintenance"
- Load balancing: "Recommend using Gun B for better distribution"

### Maintenance Tracking
When a gun needs maintenance:
1. Update status to `'maintenance'`
2. System prevents new bookings for that gun
3. Log maintenance events with gun ID
4. Update status to `'available'` when ready

### Usage Analytics
Track per-gun usage:
- Energy delivered per gun
- Revenue per gun
- Peak usage times
- Reliability metrics

## Status Values

- **available**: Gun is ready for use
- **in_use**: Gun is currently in use (session active)
- **offline**: Gun is disconnected or unavailable
- **maintenance**: Gun is undergoing maintenance

## QR/Barcode Format

- **QR Format**: `QR-{STATION_CODE}-{CONNECTOR_ID}-{GUN_NUMBER}`
  - Example: `QR-JGD-1-1` = Jangareddy Gudem, Connector 1, Gun 1

- **Barcode Format**: `BC-{STATION_CODE}-{CONNECTOR_ID}-{GUN_NUMBER}`
  - Example: `BC-JGD-1-1` = Jangareddy Gudem, Connector 1, Gun 1

## Integration Tips

1. **Mobile App**:
   - Add barcode scanner library (e.g., ML Kit for Android/iOS)
   - Display gun availability in real-time
   - Show gun location on map if available

2. **Web Dashboard**:
   - Print QR codes for each gun
   - Display usage heatmaps
   - Track maintenance schedules

3. **IoT Integration**:
   - Webhook when gun status changes
   - Automatic status update when session starts/ends
   - Real-time gun availability sync

## Error Handling

```
Gun not found in connector:
{
  "detail": "Charging gun not found for this connector"
}

Gun is unavailable:
{
  "detail": "Charging gun is maintenance"
}

QR/Barcode not found:
{
  "detail": "Charging gun QR code not found"
}
```

## Performance Optimizations

- Indexed lookups on `qr_code` and `barcode_code` for O(1) gun discovery
- Indexed `connector_id` for efficient gun listing per connector
- Indexed `charging_guns.status` for availability queries
- Aggregated gun data in station responses to reduce API calls

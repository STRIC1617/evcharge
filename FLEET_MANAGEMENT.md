# Fleet Management System

## Overview

The EV Charge API now supports fleet management, allowing organizations and companies to manage multiple vehicles and drivers efficiently. The fleet system complements individual user functionality while providing enterprise-level features.

## Key Concepts

### Fleets
A fleet is a collection of vehicles and drivers managed by an organization. Each fleet has:
- **Owner**: The user who created the fleet (cannot be changed)
- **Members**: Users assigned to the fleet with specific roles
- **Vehicles**: Cars available for use within the fleet
- **Billing**: Consolidated invoices tracking fleet-wide charges

### Member Roles

Fleet members have three role levels:

1. **Admin**
   - Full access to fleet management
   - Can add/remove members
   - Can manage vehicles and roles
   - Can view billing and invoices
   - Can update fleet information
   - Cannot delete the fleet (only owner can)

2. **Manager**
   - Can manage fleet vehicles
   - Can view fleet members and statistics
   - Can add/remove vehicles from fleet
   - Can assign vehicles to drivers
   - Cannot add/remove members

3. **Driver**
   - Can book and charge fleet vehicles
   - Can view their assigned vehicles
   - Can see fleet statistics
   - Cannot manage members or vehicles

### Vehicle Ownership Models

The system supports two vehicle models:

1. **Fleet-Owned Vehicles**
   - Created and managed by the fleet
   - Can be shared among multiple drivers
   - Billing attributed to the fleet

2. **User-Contributed Vehicles**
   - Vehicles originally created by users
   - Added to fleet for shared use
   - Original owner retains some rights

## API Endpoints

### Fleet Management

#### Create Fleet
```http
POST /api/fleets
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "Acme Delivery Fleet",
  "description": "Fleet for delivery operations",
  "billing_contact_name": "John Doe",
  "billing_contact_email": "john@acme.com",
  "billing_contact_phone": "+1-555-0123"
}
```

Response: `201 Created`
```json
{
  "id": 1,
  "name": "Acme Delivery Fleet",
  "description": "Fleet for delivery operations",
  "owner_id": 5,
  "billing_contact_name": "John Doe",
  "billing_contact_email": "john@acme.com",
  "billing_contact_phone": "+1-555-0123",
  "status": "active",
  "created_at": "2026-07-18T10:30:00",
  "updated_at": "2026-07-18T10:30:00"
}
```

#### List User's Fleets
```http
GET /api/fleets
Authorization: Bearer <token>
```

Response:
```json
[
  {
    "id": 1,
    "name": "Acme Delivery Fleet",
    "description": "Fleet for delivery operations",
    "owner_id": 5,
    "billing_contact_name": "John Doe",
    "billing_contact_email": "john@acme.com",
    "billing_contact_phone": "+1-555-0123",
    "status": "active",
    "created_at": "2026-07-18T10:30:00",
    "updated_at": "2026-07-18T10:30:00",
    "role": "admin"
  }
]
```

#### Get Fleet Details
```http
GET /api/fleets/{fleet_id}
Authorization: Bearer <token>
```

#### Update Fleet
```http
PATCH /api/fleets/{fleet_id}
Content-Type: application/json
Authorization: Bearer <token>

{
  "name": "Updated Fleet Name",
  "billing_contact_email": "newemail@acme.com"
}
```

#### Delete Fleet
```http
DELETE /api/fleets/{fleet_id}
Authorization: Bearer <token>
```

Only the fleet owner can delete the fleet.

### Member Management

#### Add Member to Fleet
```http
POST /api/fleets/{fleet_id}/members
Content-Type: application/json
Authorization: Bearer <token>

{
  "user_id": 10,
  "role": "driver"
}
```

Valid roles: `admin`, `manager`, `driver`

#### List Fleet Members
```http
GET /api/fleets/{fleet_id}/members
Authorization: Bearer <token>
```

Response:
```json
[
  {
    "id": 1,
    "fleet_id": 1,
    "user_id": 5,
    "role": "admin",
    "joined_at": "2026-07-18T10:30:00",
    "updated_at": "2026-07-18T10:30:00",
    "email": "john@acme.com",
    "name": "John Doe",
    "phone": "+1-555-0123"
  },
  {
    "id": 2,
    "fleet_id": 1,
    "user_id": 10,
    "role": "driver",
    "joined_at": "2026-07-18T11:00:00",
    "updated_at": "2026-07-18T11:00:00",
    "email": "driver@acme.com",
    "name": "Jane Smith",
    "phone": "+1-555-0456"
  }
]
```

#### Update Member Role
```http
PATCH /api/fleets/{fleet_id}/members/{user_id}?role=manager
Authorization: Bearer <token>
```

#### Remove Member from Fleet
```http
DELETE /api/fleets/{fleet_id}/members/{user_id}
Authorization: Bearer <token>
```

Cannot remove the fleet owner.

### Vehicle Management

#### Add Vehicle to Fleet
```http
POST /api/fleets/{fleet_id}/vehicles
Content-Type: application/json
Authorization: Bearer <token>

{
  "vehicle_id": 15,
  "assigned_to_user_id": 10,
  "is_shared": true
}
```

- `vehicle_id`: ID of the vehicle (must exist in system)
- `assigned_to_user_id`: (Optional) Assign to a specific fleet member
- `is_shared`: Whether vehicle can be used by multiple drivers

#### List Fleet Vehicles
```http
GET /api/fleets/{fleet_id}/vehicles
Authorization: Bearer <token>
```

Response:
```json
[
  {
    "id": 1,
    "fleet_id": 1,
    "vehicle_id": 15,
    "assigned_to_user_id": 10,
    "is_shared": true,
    "status": "active",
    "added_at": "2026-07-18T10:35:00",
    "updated_at": "2026-07-18T10:35:00",
    "make": "Tesla",
    "model": "Model 3",
    "year": 2024,
    "battery_capacity_kwh": 75,
    "connector_type": "CCS2",
    "license_plate": "ACM-2024-01",
    "assigned_to_name": "Jane Smith"
  }
]
```

#### Update Vehicle Assignment
```http
PATCH /api/fleets/{fleet_id}/vehicles/{vehicle_id}
Content-Type: application/json
Authorization: Bearer <token>

{
  "assigned_to_user_id": 11,
  "is_shared": false
}
```

#### Remove Vehicle from Fleet
```http
DELETE /api/fleets/{fleet_id}/vehicles/{vehicle_id}
Authorization: Bearer <token>
```

### Billing & Analytics

#### Get Fleet Invoices
```http
GET /api/fleets/{fleet_id}/invoices
Authorization: Bearer <token>
```

Response:
```json
[
  {
    "id": 1,
    "fleet_id": 1,
    "billing_period_start": "2026-07-01",
    "billing_period_end": "2026-07-31",
    "total_sessions": 45,
    "total_energy_kwh": 1234.56,
    "amount": 308.64,
    "tax_amount": 30.86,
    "total_amount": 339.50,
    "status": "pending",
    "due_date": "2026-08-15",
    "paid_at": null,
    "created_at": "2026-08-01T00:00:00",
    "updated_at": "2026-08-01T00:00:00"
  }
]
```

#### Get Fleet Statistics
```http
GET /api/fleets/{fleet_id}/stats
Authorization: Bearer <token>
```

Response:
```json
{
  "fleet_id": 1,
  "total_sessions": 45,
  "total_energy_kwh": 1234.56,
  "total_cost": 308.64,
  "unique_drivers": 8,
  "vehicles_used": 6
}
```

## Usage Workflow

### 1. Create a Fleet
```bash
curl -X POST http://localhost:8000/api/fleets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Company Fleet",
    "description": "Company vehicles for business operations"
  }'
```

### 2. Add Fleet Members
```bash
curl -X POST http://localhost:8000/api/fleets/1/members \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 5,
    "role": "manager"
  }'
```

### 3. Create Vehicles
```bash
curl -X POST http://localhost:8000/api/users/vehicles \
  -H "Authorization: Bearer $USER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "make": "Tesla",
    "model": "Model 3",
    "year": 2024,
    "connector_type": "CCS2"
  }'
```

### 4. Add Vehicles to Fleet
```bash
curl -X POST http://localhost:8000/api/fleets/1/vehicles \
  -H "Authorization: Bearer $MANAGER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "vehicle_id": 3,
    "is_shared": true
  }'
```

### 5. Book and Charge with Fleet Vehicles
When booking, specify `fleet_id` to use fleet vehicles:
```bash
curl -X POST http://localhost:8000/api/bookings \
  -H "Authorization: Bearer $DRIVER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "fleet_id": 1,
    "vehicle_id": 3,
    "station_id": 2,
    "connector_id": 5,
    "start_time": "2026-07-20T10:00:00",
    "end_time": "2026-07-20T12:00:00"
  }'
```

### 6. Track Fleet Billing
```bash
curl http://localhost:8000/api/fleets/1/invoices \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Permission Matrix

| Action | Admin | Manager | Driver |
|--------|-------|---------|--------|
| Create Fleet | ✓ | ✗ | ✗ |
| Edit Fleet | ✓ | ✗ | ✗ |
| Delete Fleet | Owner only | ✗ | ✗ |
| Add Members | ✓ | ✗ | ✗ |
| Remove Members | ✓ | ✗ | ✗ |
| Change Member Role | ✓ | ✗ | ✗ |
| Add Vehicles | ✓ | ✓ | ✗ |
| Remove Vehicles | ✓ | ✓ | ✗ |
| Assign Vehicle | ✓ | ✓ | ✗ |
| Book Fleet Vehicle | ✓ | ✓ | ✓ |
| View Stats | ✓ | ✓ | ✓ |
| View Invoices | ✓ | ✗ | ✗ |

## Database Schema

### fleets
```sql
id INTEGER PRIMARY KEY
name VARCHAR(255) NOT NULL
description TEXT
owner_id INTEGER (references users)
billing_contact_name VARCHAR(255)
billing_contact_email VARCHAR(255)
billing_contact_phone VARCHAR(50)
status VARCHAR(50) DEFAULT 'active'
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### fleet_members
```sql
id INTEGER PRIMARY KEY
fleet_id INTEGER (references fleets)
user_id INTEGER (references users)
role VARCHAR(50) - admin | manager | driver
joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
UNIQUE(fleet_id, user_id)
```

### fleet_vehicles
```sql
id INTEGER PRIMARY KEY
fleet_id INTEGER (references fleets)
vehicle_id INTEGER (references vehicles)
assigned_to_user_id INTEGER (references users)
is_shared BOOLEAN DEFAULT false
status VARCHAR(50) DEFAULT 'active'
added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
UNIQUE(fleet_id, vehicle_id)
```

### fleet_invoices
```sql
id INTEGER PRIMARY KEY
fleet_id INTEGER (references fleets)
billing_period_start DATE
billing_period_end DATE
total_sessions INTEGER
total_energy_kwh DECIMAL(10,3)
amount DECIMAL(10,2)
tax_amount DECIMAL(10,2)
total_amount DECIMAL(10,2)
status VARCHAR(50) DEFAULT 'pending'
due_date DATE
paid_at TIMESTAMP
created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

## Best Practices

1. **Role Assignment**: Assign managers for day-to-day operations, keep admins for sensitive changes
2. **Vehicle Sharing**: Use `is_shared: true` for vehicles used by multiple drivers
3. **Billing Contact**: Keep billing information updated for accurate invoice delivery
4. **Regular Audits**: Review fleet members and vehicles periodically
5. **Driver Training**: Ensure drivers understand which vehicles they can use

## Error Responses

Common error scenarios:

```json
{
  "detail": "You do not have access to this fleet"
}
```

Status: 403 Forbidden

```json
{
  "detail": "User is not a member of this fleet"
}
```

Status: 400 Bad Request

```json
{
  "detail": "Vehicle is already in this fleet"
}
```

Status: 400 Bad Request

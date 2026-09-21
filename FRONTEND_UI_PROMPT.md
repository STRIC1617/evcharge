# 🎨 Frontend UI/UX Prompt - Charging Gun Selection System

## Project Overview
Mobile and web frontend for EV charging station booking with advanced charging gun selection via QR codes, barcodes, or manual selection.

---

## 📱 MOBILE APP - FRONTEND SCREENS

### Screen 1: Home Dashboard
**Purpose**: Main entry point for users

**Layout**:
```
┌─────────────────────────────────┐
│  ChargeConnect                  │
│  🔋 EV Charging Network         │
├─────────────────────────────────┤
│                                 │
│  ⚡ Quick Actions               │
│  ┌─────────────────────────────┐│
│  │ 📱 Scan QR Code             ││ (Button)
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ 🔍 Scan Barcode             ││ (Button)
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ 📍 Find Nearby Stations     ││ (Button)
│  └─────────────────────────────┘│
│                                 │
│  📋 Recent Bookings             │
│  ┌─────────────────────────────┐│
│  │ Jangareddy Gudem EV Hub     ││
│  │ 🔌 DC Fast 1 - Gun A        ││
│  │ July 20, 10:00 AM           ││
│  │ Status: Confirmed ✓         ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ Visakhapatnam Charging Hub  ││
│  │ 🔌 AC Type2 - Gun B         ││
│  │ July 21, 02:30 PM           ││
│  │ Status: Pending ⏳          ││
│  └─────────────────────────────┘│
│                                 │
│  👤 Account | 📧 Notifications │
└─────────────────────────────────┘
```

**UI Elements**:
- Header with logo and greeting
- Four action buttons (QR scan, Barcode scan, Find nearby, Manual search)
- Recent bookings carousel
- Bottom navigation: Home, Search, Bookings, Account

**User Interactions**:
- Tap "Scan QR Code" → Navigate to Screen 2
- Tap "Scan Barcode" → Navigate to Screen 2b
- Tap "Find Nearby Stations" → Navigate to Screen 3
- Tap booking card → Navigate to Screen 7

---

### Screen 2: QR Code Scanner
**Purpose**: Scan QR codes on charging guns for instant booking

**Layout**:
```
┌─────────────────────────────────┐
│ ← Back                QR Scanner │
├─────────────────────────────────┤
│                                 │
│    📷 Camera Preview            │
│    ┌─────────────────────────┐  │
│    │                         │  │
│    │   [Live camera feed]    │  │
│    │   With QR code overlay  │  │
│    │                         │  │
│    │      🎯 Focus area      │  │
│    │                         │  │
│    │                         │  │
│    └─────────────────────────┘  │
│                                 │
│  💡 Point camera at QR code     │
│  on the charging gun            │
│                                 │
│  ┌─────────────────────────────┐│
│  │ 🔦 Toggle Flash             ││
│  └─────────────────────────────┘│
│                                 │
│  Or ┌──────────────────────────┐│
│     │ 📁 Upload QR Image       │││
│     └──────────────────────────┘│
│                                 │
└─────────────────────────────────┘
```

**UI Elements**:
- Full-screen camera feed
- Rectangular overlay showing scan area
- Flash toggle button
- Upload image option
- Back button
- Scanning indicator with animated border
- Vibration feedback on successful scan

**User Interactions**:
- Point camera at QR code
- System auto-detects and scans
- On successful scan → Navigate to Screen 4 (Gun Details) with QR code data

**API Call**:
```
GET /api/stations/gun/qr/{qr_code}

Response:
{
  "id": 1,
  "gun_number": 1,
  "gun_name": "Gun A",
  "qr_code": "QR-JGD-1-1",
  "status": "available",
  "connector_id": 1,
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

---

### Screen 2b: Barcode Code Scanner
**Purpose**: Scan barcode codes on charging guns

**Layout**: Same as Screen 2, but:
- Title: "Barcode Scanner"
- Instruction text: "Point camera at barcode on the charging gun"
- Barcode-specific overlay pattern

**User Interactions**:
- Scan barcode (e.g., BC-JGD-1-1)
- On successful scan → Navigate to Screen 4 (Gun Details)

**API Call**:
```
GET /api/stations/gun/barcode/{barcode_code}

Response: Same as QR lookup
```

---

### Screen 3: Find Nearby Stations
**Purpose**: Discover charging stations with available guns nearby

**Layout**:
```
┌─────────────────────────────────┐
│ ← Back              Nearby Guns  │
├─────────────────────────────────┤
│  📍 Location enabled             │
│  [Current: 17.1200°N, 81.3000°E]│
│  ┌──────────────────────────────┐│
│  │ 🔄 Refresh  │  🗺️ Map View │  │
│  └──────────────────────────────┘│
│                                 │
│  STATIONS NEARBY (Sorted by km) │
│  ┌─────────────────────────────┐│
│  │ 0.5 km away                 ││
│  │ ⭐ Jangareddy Gudem EV Hub  ││
│  │ 📍 Main Road, Jangareddy... ││
│  │                             ││
│  │ Available Guns:             ││
│  │ 🔌 DC Fast 1                ││
│  │   • Gun A (QR-JGD-1-1) ✓    ││
│  │   • Gun B (QR-JGD-1-2) ✓    ││
│  │ 🔌 DC Fast 2                ││
│  │   • Gun A (QR-JGD-2-1) ✓    ││
│  │   • Gun B (QR-JGD-2-2) 🔧   ││ (maintenance)
│  │ 🔌 AC Type2                 ││
│  │   • Gun A (QR-JGD-3-1) ✓    ││
│  │                             ││
│  │ [Book Now] [View Details]   ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ 2.3 km away                 ││
│  │ ⭐ Visakhapatnam Hub        ││
│  │ 📍 Port Road, Visakhapat... ││
│  │                             ││
│  │ Available Guns:             ││
│  │ 🔌 Tesla Supercharger       ││
│  │   • Gun A (QR-VIZ-1-1) ✓    ││
│  │ 🔌 CCS2 Fast                ││
│  │   • Gun A (QR-VIZ-2-1) 🔴   ││ (offline)
│  │                             ││
│  │ [Book Now] [View Details]   ││
│  └─────────────────────────────┘│
│                                 │
└─────────────────────────────────┘
```

**Status Indicators**:
- ✓ Green: Available
- 🔧 Orange: Maintenance
- 🔴 Red: Offline
- ⏳ Gray: In Use

**UI Elements**:
- Location display with precision
- Refresh button
- Map view toggle (shows pins for stations)
- Station cards with scrollable list
- Gun availability with status badges
- Action buttons: "Book Now", "View Details"
- Distance calculation and sorting

**User Interactions**:
- Tap "Book Now" → Navigate to Screen 5 (Select Charging Gun)
- Tap "View Details" → Navigate to Screen 6 (Station Details)
- Tap map view → Show stations on map with gun counts

**API Call**:
```
GET /api/stations/nearby?lat=17.1200&lng=81.3000&include_connectors=true&include_guns=true

Response:
[
  {
    "id": 1,
    "name": "Jangareddy Gudem EV Hub",
    "address": "Main Road...",
    "latitude": 17.1200,
    "longitude": 81.3000,
    "distance_km": 0.5,
    "connectors": [
      {
        "id": 1,
        "name": "DC Fast 1",
        "connector_type": "CCS2",
        "power_type": "DC",
        "max_power_kw": 150,
        "status": "available",
        "charging_guns": [
          {
            "id": 1,
            "gun_number": 1,
            "gun_name": "Gun A",
            "qr_code": "QR-JGD-1-1",
            "status": "available"
          }
        ]
      }
    ]
  }
]
```

---

### Screen 4: Gun Details (Post-Scan)
**Purpose**: Show gun details after scanning QR/barcode

**Layout**:
```
┌─────────────────────────────────┐
│ ← Back          Charging Gun     │
├─────────────────────────────────┤
│                                 │
│  ✓ Gun Found!                   │
│                                 │
│  🔌 DC Fast Charging            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                 │
│  Gun ID: Gun A                  │
│  Code: QR-JGD-1-1               │
│  Status: ✓ Available            │
│                                 │
│  📍 Jangareddy Gudem EV Hub     │
│  Main Road, Near Bus Stand      │
│  Jangareddy Gudem, West         │
│  Godavari, Andhra Pradesh       │
│                                 │
│  Connector Details:             │
│  ├─ Type: CCS2                  │
│  ├─ Power: DC                   │
│  └─ Max: 150 kW                 │
│                                 │
│  💰 Pricing:                    │
│  ├─ Per kWh: ₹0.35              │
│  ├─ Per Min: ₹0.00              │
│  └─ Max Power: 150 kW           │
│                                 │
│  ⭐ Rating: 4.8/5 (245 reviews)  │
│  📊 Amenities:                  │
│  WiFi • Restroom • Coffee • Parking
│                                 │
│  Last Used: Today, 2:30 PM      │
│                                 │
│  ┌─────────────────────────────┐│
│  │ 🗺️ Show Map                 ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ ✓ Book This Gun             ││
│  └─────────────────────────────┘│
│                                 │
└─────────────────────────────────┘
```

**UI Elements**:
- Gun status badge (green/orange/red)
- Station location with map link
- Connector specs
- Pricing information
- Station ratings and reviews
- Last usage time
- "Show Map" button
- "Book This Gun" CTA button

**User Interactions**:
- Tap "Show Map" → Open map with station location
- Tap "Book This Gun" → Navigate to Screen 5 (Booking Details)
- Tap back → Return to home or scan screen

---

### Screen 5: Booking Details & Confirmation
**Purpose**: Select time slots and confirm charging gun booking

**Layout**:
```
┌─────────────────────────────────┐
│ ← Back              Book Charging│
├─────────────────────────────────┤
│  Charging Gun: Gun A             │
│  Station: Jangareddy Gudem      │
│  Connector: DC Fast 1 (CCS2)    │
│  Status: ✓ Available            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                 │
│  📅 Select Date & Time          │
│  ┌─────────────────────────────┐│
│  │ Date ▼                      ││
│  │ [Select Date]               ││
│  └─────────────────────────────┘│
│                                 │
│  ⏰ Start Time                  │
│  ┌─────────────────────────────┐│
│  │ Time ▼                      ││
│  │ 10:00 AM                    ││
│  └─────────────────────────────┘│
│                                 │
│  ⏱️ End Time                    │
│  ┌─────────────────────────────┐│
│  │ Time ▼                      ││
│  │ 12:00 PM (2 hours)          ││
│  └─────────────────────────────┘│
│                                 │
│  🚗 Vehicle Selection           │
│  ┌─────────────────────────────┐│
│  │ Select Vehicle ▼            ││
│  │ [2020 Tesla Model 3]        ││
│  │ [2022 Hyundai Kona Electric]││
│  │ [Add New Vehicle]           ││
│  └─────────────────────────────┘│
│                                 │
│  👥 Fleet (Optional)            │
│  ┌─────────────────────────────┐│
│  │ Select Fleet ▼              ││
│  │ [No Fleet]                  ││
│  │ [Company Fleet A]           ││
│  │ [Company Fleet B]           ││
│  └─────────────────────────────┘│
│                                 │
│  💳 Pricing Estimate            │
│  ├─ Unit Rate: ₹0.35/kWh       │
│  ├─ Est. Usage: 20 kWh         │
│  ├─ Subtotal: ₹7.00            │
│  ├─ Tax (5%): ₹0.35            │
│  └─ Total: ₹7.35               │
│                                 │
│  ⚠️ Cancellation Policy         │
│  Free cancellation up to        │
│  15 mins before start time      │
│                                 │
│  ┌─────────────────────────────┐│
│  │ 📋 View Full Terms          ││
│  └─────────────────────────────┘│
│                                 │
│  ┌─────────────────────────────┐│
│  │ ✓ Confirm Booking           ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ ✗ Cancel                   ││
│  └─────────────────────────────┘│
│                                 │
└─────────────────────────────────┘
```

**Form Validation**:
- Date must be today or future
- End time must be after start time
- Maximum booking duration: 24 hours
- Vehicle is required
- Show real-time availability
- Display time slot conflicts

**UI Elements**:
- Gun/Station summary at top
- Date picker (calendar view)
- Time picker (start & end)
- Vehicle dropdown with add option
- Fleet selector (optional)
- Price breakdown
- Cancellation policy summary
- Terms link
- Confirm/Cancel buttons

**User Interactions**:
- Select date → Update calendar availability
- Select start time → Auto-update end time suggestions
- Select vehicle → Enable booking if not already enabled
- Toggle fleet → Show fleet-specific pricing (if applicable)
- Tap "Confirm Booking" → Navigate to Screen 8 (Confirmation)
- Tap "Cancel" → Return to previous screen

**API Call**:
```
POST /api/bookings
Content-Type: application/json
Authorization: Bearer <token>

{
  "station_id": 1,
  "connector_id": 1,
  "charging_gun_id": 1,
  "vehicle_id": 5,
  "fleet_id": null,
  "start_time": "2026-07-20T10:00:00",
  "end_time": "2026-07-20T12:00:00"
}

Response (201 Created):
{
  "id": 15,
  "user_id": 3,
  "station_id": 1,
  "connector_id": 1,
  "charging_gun_id": 1,
  "vehicle_id": 5,
  "fleet_id": null,
  "status": "confirmed",
  "start_time": "2026-07-20T10:00:00",
  "end_time": "2026-07-20T12:00:00",
  "pricing_snapshot": {
    "price_per_kwh": 0.35,
    "price_per_minute": 0.0,
    "max_power_kw": 150
  },
  "created_at": "2026-07-18T15:30:00",
  "updated_at": "2026-07-18T15:30:00"
}
```

---

### Screen 6: Station Details
**Purpose**: View complete station information with all available guns

**Layout**:
```
┌─────────────────────────────────┐
│ ← Back              Station Info │
├─────────────────────────────────┤
│                                 │
│  🏢 Jangareddy Gudem EV Hub    │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                 │
│  ⭐ 4.8/5 (245 reviews)         │
│  📍 Main Road, Near Bus Stand   │
│  Jangareddy Gudem, West         │
│  Godavari, AP 534001            │
│  ☎️ +91-9999-999-999            │
│                                 │
│  🗺️ [View Map] [Directions]    │
│                                 │
│  AMENITIES                      │
│  ┌─────────────────────────────┐│
│  │ 📡 WiFi                     ││
│  │ 🚽 Restroom                 ││
│  │ ☕ Coffee Shop              ││
│  │ 🅿️ Parking (50 spots)       ││
│  │ 🏪 Restaurant               ││
│  │ 🛒 Small Shop               ││
│  └─────────────────────────────┘│
│                                 │
│  AVAILABLE CHARGING GUNS        │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│  🔌 DC Fast Charging - 150kW    │
│  ┌─────────────────────────────┐│
│  │ Connector 1: DC Fast 1      ││
│  │ Type: CCS2 | Power: DC      ││
│  │ Price: ₹0.35/kWh           ││
│  │                             ││
│  │ ✓ Gun A (QR-JGD-1-1)        ││
│  │ ✓ Gun B (QR-JGD-1-2)        ││
│  │ [Book Gun A] [Book Gun B]   ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ Connector 2: DC Fast 2      ││
│  │ Type: CCS2 | Power: DC      ││
│  │ Price: ₹0.35/kWh           ││
│  │                             ││
│  │ ✓ Gun A (QR-JGD-2-1)        ││
│  │ 🔧 Gun B (QR-JGD-2-2)       ││
│  │ [Book Gun A]                ││
│  └─────────────────────────────┘│
│                                 │
│  🔌 AC Type2 Charging - 22kW    │
│  ┌─────────────────────────────┐│
│  │ Connector 3: AC Type2       ││
│  │ Type: Type2 | Power: AC     ││
│  │ Price: ₹0.15/kWh           ││
│  │                             ││
│  │ ✓ Gun A (QR-JGD-3-1)        ││
│  │ [Book Gun A]                ││
│  └─────────────────────────────┘│
│                                 │
│  REVIEWS (4.8/5)                │
│  ┌─────────────────────────────┐│
│  │ ⭐⭐⭐⭐⭐ Excellent service  ││
│  │ "Fast charging, clean       ││
│  │  environment, very helpful  ││
│  │  staff"                     ││
│  │ - Rajesh K, 2 days ago      ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ ⭐⭐⭐⭐ Great location      ││
│  │ "Conveniently located near  ││
│  │  the main road, reasonable  ││
│  │  pricing"                   ││
│  │ - Priya M, 1 week ago       ││
│  └─────────────────────────────┘│
│                                 │
│  [See More Reviews]             │
│                                 │
└─────────────────────────────────┘
```

**UI Elements**:
- Station header with rating
- Contact information
- Address and directions
- Amenities grid with icons
- All connectors with guns listed
- Gun status indicators
- "Book" button for each gun
- Reviews section (last 3-4)
- View more reviews link

**User Interactions**:
- Tap [Directions] → Open maps app
- Tap [View Map] → Show station on map
- Tap [Book Gun A] → Navigate to Screen 5 (Booking Details)
- Tap [See More Reviews] → Navigate to Screen 9 (Reviews)

**API Call**:
```
GET /api/stations/{station_id}?include_connectors=true&include_guns=true
```

---

### Screen 7: Booking Details View
**Purpose**: View confirmed booking details

**Layout**:
```
┌─────────────────────────────────┐
│ ← Back              Booking      │
├─────────────────────────────────┤
│  Booking ID: #15                │
│  Status: ✓ Confirmed            │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━  │
│                                 │
│  🔌 CHARGING GUN                │
│  Station: Jangareddy Gudem      │
│  Connector: DC Fast 1 (CCS2)    │
│  Gun: Gun A                     │
│  QR Code: QR-JGD-1-1            │
│  Barcode: BC-JGD-1-1            │
│                                 │
│  🚗 VEHICLE                     │
│  2020 Tesla Model 3             │
│  License: TG-01-AB-1234         │
│                                 │
│  📅 SCHEDULE                    │
│  Date: July 20, 2026            │
│  Start: 10:00 AM                │
│  End: 12:00 PM                  │
│  Duration: 2 hours              │
│                                 │
│  💰 PRICING                     │
│  ├─ Rate: ₹0.35/kWh             │
│  ├─ Estimated: 20 kWh           │
│  ├─ Subtotal: ₹7.00             │
│  ├─ Tax (5%): ₹0.35             │
│  └─ Total: ₹7.35                │
│                                 │
│  ⚠️ CANCELLATION                │
│  Free cancellation until:       │
│  July 20, 9:45 AM               │
│  (15 minutes before start)      │
│                                 │
│  📍 LOCATION                    │
│  Main Road, Near Bus Stand      │
│  Jangareddy Gudem, West         │
│  Godavari, AP 534001            │
│  ☎️ +91-9999-999-999            │
│                                 │
│  ┌─────────────────────────────┐│
│  │ 🗺️ View Location            ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ 📍 Get Directions           ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ ⏰ Set Reminder             ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ 🔔 Modify Booking           ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ ❌ Cancel Booking           ││
│  └─────────────────────────────┘│
│                                 │
│  🎟️ Show QR Code                │
│  ┌─────────────────────────────┐│
│  │ [Large QR Code Display]     ││
│  │ (for scanning at station)   ││
│  └─────────────────────────────┘│
│                                 │
│  Booking Confirmation Sent to:  │
│  📧 user@example.com            │
│                                 │
└─────────────────────────────────┘
```

**UI Elements**:
- Booking ID and status badge
- Gun details with QR/barcode codes
- Vehicle information
- Schedule details
- Price breakdown
- Cancellation deadline and policy
- Station location and contact
- Action buttons: Map, Directions, Reminder, Modify, Cancel
- Large QR code display for check-in
- Confirmation email notification

**User Interactions**:
- Tap [View Location] → Open map
- Tap [Get Directions] → Open navigation app
- Tap [Set Reminder] → Enable notification before booking
- Tap [Modify Booking] → Navigate to Screen 5 with pre-filled data
- Tap [Cancel Booking] → Show confirmation dialog → Cancel via API
- Display QR code for easy check-in at station

**API Call**:
```
GET /api/bookings/{booking_id}

Response:
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
  "station_name": "Jangareddy Gudem EV Hub",
  "station_address": "Main Road, Near Bus Stand, Jangareddy Gudem, West Godavari, Andhra Pradesh",
  "connector_name": "DC Fast 1",
  "connector_type": "CCS2",
  "power_type": "DC",
  "max_power_kw": 150,
  "gun_name": "Gun A",
  "qr_code": "QR-JGD-1-1",
  "barcode_code": "BC-JGD-1-1",
  "pricing_snapshot": {
    "price_per_kwh": 0.35,
    "price_per_minute": 0.0,
    "max_power_kw": 150,
    "captured_at": "2026-07-18T15:30:00"
  }
}
```

---

### Screen 8: Booking Confirmation
**Purpose**: Show immediate booking confirmation

**Layout**:
```
┌─────────────────────────────────┐
│          ✓ SUCCESS!             │
│                                 │
│     🎉 Booking Confirmed        │
│                                 │
│  Booking ID: #15                │
│                                 │
│  Gun: Jangareddy Gudem          │
│       Gun A (DC Fast 1)         │
│                                 │
│  Date: July 20, 2026            │
│  Time: 10:00 AM - 12:00 PM     │
│                                 │
│  Total: ₹7.35                   │
│                                 │
│  ✓ Confirmation email sent      │
│                                 │
│  Next Steps:                    │
│  1. Keep booking ID handy       │
│  2. Arrive at station 5 mins    │
│     before scheduled time       │
│  3. Scan QR code at gun to      │
│     start charging              │
│  4. Connect your vehicle        │
│                                 │
│  ⏰ Cancellation allowed until:  │
│     July 20, 9:45 AM            │
│                                 │
│  ┌─────────────────────────────┐│
│  │ 👁️ View Booking Details     ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ 🏠 Back to Home             ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ 📍 Get Directions           ││
│  └─────────────────────────────┘│
│                                 │
└─────────────────────────────────┘
```

**UI Elements**:
- Large success checkmark animation
- Booking ID (copyable)
- Gun and station details
- Time summary
- Total price
- Email confirmation notification
- Step-by-step instructions
- Cancellation deadline
- Action buttons

**User Interactions**:
- Tap [View Booking Details] → Navigate to Screen 7
- Tap [Back to Home] → Navigate to Screen 1
- Tap [Get Directions] → Open navigation app
- Tap booking ID → Copy to clipboard

---

### Screen 9: My Bookings List
**Purpose**: View all bookings with filtering and status tracking

**Layout**:
```
┌─────────────────────────────────┐
│ ← Back              My Bookings  │
├─────────────────────────────────┤
│  Filter: ▼                      │
│  [ All ] [ Upcoming ] [Past]    │
│  [ Confirmed ] [ Pending ]      │
│                                 │
│  UPCOMING BOOKINGS              │
│  ┌─────────────────────────────┐│
│  │ Booking #15                 ││
│  │ ⚡ Jangareddy Gudem EV Hub  ││
│  │ 🔌 DC Fast 1 - Gun A        ││
│  │ 📅 July 20, 2026            ││
│  │ ⏰ 10:00 AM - 12:00 PM     ││
│  │ 💰 ₹7.35                    ││
│  │ ✓ Confirmed                 ││
│  │ [Details] [Cancel]          ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ Booking #14                 ││
│  │ ⚡ Visakhapatnam Hub        ││
│  │ 🔌 AC Type2 - Gun B         ││
│  │ 📅 July 21, 2026            ││
│  │ ⏰ 02:30 PM - 04:30 PM     ││
│  │ 💰 ₹3.15                    ││
│  │ ⏳ Pending                   ││
│  │ [Details] [Cancel]          ││
│  └─────────────────────────────┘│
│                                 │
│  PAST BOOKINGS                  │
│  ┌─────────────────────────────┐│
│  │ Booking #13                 ││
│  │ ⚡ Hyderabad Charging Hub   ││
│  │ 🔌 Tesla Supercharger       ││
│  │ 📅 July 15, 2026            ││
│  │ ⏰ 11:00 AM - 01:00 PM     ││
│  │ 💰 ₹12.50                   ││
│  │ ✓ Completed                 ││
│  │ [Details] [Rebook]          ││
│  └─────────────────────────────┘│
│  ┌─────────────────────────────┐│
│  │ Booking #12                 ││
│  │ ⚡ Tirupati Charging Hub    ││
│  │ 🔌 CCS2 Fast - Gun A        ││
│  │ 📅 July 10, 2026            ││
│  │ ⏰ 03:00 PM - 05:00 PM     ││
│  │ 💰 ₹8.75                    ││
│  │ ❌ Cancelled                ││
│  │ [Details]                   ││
│  └─────────────────────────────┘│
│                                 │
│  [Load More...]                 │
│                                 │
└─────────────────────────────────┘
```

**Status Badges**:
- ✓ Confirmed (Green)
- ⏳ Pending (Yellow)
- ✓ Completed (Green)
- ❌ Cancelled (Gray)

**UI Elements**:
- Filter tabs: All, Upcoming, Past
- Status filter options
- Booking cards with all details
- Gun and connector info
- Price display
- Action buttons per status
- Load more pagination

**User Interactions**:
- Tap filter → Update list
- Tap booking card → Navigate to Screen 7 (Details)
- Tap [Details] → Navigate to Screen 7
- Tap [Cancel] (upcoming) → Show cancellation dialog
- Tap [Rebook] (past) → Navigate to Screen 5 with vehicle pre-selected

**API Call**:
```
GET /api/bookings

Response:
[
  {
    "id": 15,
    "station_name": "Jangareddy Gudem EV Hub",
    "connector_name": "DC Fast 1",
    "gun_name": "Gun A",
    "qr_code": "QR-JGD-1-1",
    "status": "confirmed",
    "start_time": "2026-07-20T10:00:00",
    "end_time": "2026-07-20T12:00:00",
    "pricing_snapshot": {"price_per_kwh": 0.35}
  }
]
```

---

## 🌐 WEB DASHBOARD - FRONTEND SCREENS

### Web Screen 1: Dashboard Home
**Purpose**: Admin/user dashboard overview

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│  ChargeConnect Dashboard          👤 Admin | Logout        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Quick Stats:                                               │
│  ┌──────────────┬──────────────┬──────────────┬──────────┐  │
│  │ Bookings     │ Revenue      │ Active Users │ Stations │  │
│  │    47        │  ₹2,340      │     156      │    10    │  │
│  └──────────────┴──────────────┴──────────────┴──────────┘  │
│                                                             │
│  Left Sidebar:                                              │
│  ├─ 📊 Dashboard                                            │
│  ├─ 📍 Stations                                             │
│  ├─ 🔌 Connectors                                           │
│  ├─ 🔫 Charging Guns                                        │
│  ├─ 🚗 Vehicles                                             │
│  ├─ 📅 Bookings                                             │
│  ├─ 👥 Users                                                │
│  ├─ 💳 Billing                                              │
│  ├─ ⚙️ Settings                                             │
│  └─ 🔚 Fleet Management                                     │
│                                                             │
│  Main Content:                                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 📈 Booking Trends (Last 30 Days)                    │   │
│  │  [Line chart showing bookings over time]            │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 💰 Revenue by Station                              │   │
│  │  [Bar chart showing revenue per station]            │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🔫 Gun Usage Heatmap                               │   │
│  │  [Heatmap showing which guns are most used]         │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🚨 Alerts                                           │   │
│  │  ⚠️ Gun A (JGD-1-1) needs maintenance              │   │
│  │  ⚠️ Connector 2 (VIZ-2) offline since 2 hours      │   │
│  │  ✓ 5 bookings in next hour                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### Web Screen 2: Charging Guns Management
**Purpose**: Manage all charging guns with QR/barcode codes

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ Dashboard > Charging Guns                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🔫 Charging Guns Management                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ [+ Add New Gun]                                     │   │
│  │ Filter: [ ] [ ] | Search: [________]               │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Station          Connector      Gun      QR Code      │   │
│  ────────────────────────────────────────────────────── │   │
│  Jangareddy       DC Fast 1      Gun A    QR-JGD-1-1  │   │
│  Gudem EV Hub     (CCS2, 150kW)         ✓ Available    │   │
│                                                         │   │
│  Status: ✓ available | Last Used: Today 2:30 PM      │   │
│  Actions: [View] [Edit] [QR Code] [Print] [Maintain]  │   │
│  ───────────────────────────────────────────────────── │   │
│                                                         │   │
│  Jangareddy       DC Fast 1      Gun B    QR-JGD-1-2  │   │
│  Gudem EV Hub     (CCS2, 150kW)         ✓ Available    │   │
│                                                         │   │
│  Status: ✓ available | Last Used: Yesterday 5:15 PM  │   │
│  Actions: [View] [Edit] [QR Code] [Print] [Maintain]  │   │
│  ───────────────────────────────────────────────────── │   │
│                                                         │   │
│  Jangareddy       DC Fast 2      Gun A    QR-JGD-2-1  │   │
│  Gudem EV Hub     (CCS2, 150kW)         ✓ Available    │   │
│                                                         │   │
│  Status: ✓ available | Last Used: 3 days ago         │   │
│  Actions: [View] [Edit] [QR Code] [Print] [Maintain]  │   │
│  ───────────────────────────────────────────────────── │   │
│                                                         │   │
│  Jangareddy       DC Fast 2      Gun B    QR-JGD-2-2  │   │
│  Gudem EV Hub     (CCS2, 150kW)         🔧 Maintenance│   │
│                                                         │   │
│  Status: 🔧 maintenance | Last Used: 1 hour ago      │   │
│  Actions: [View] [Edit] [QR Code] [Print] [Resume]    │   │
│  ───────────────────────────────────────────────────── │   │
│                                                         │   │
│  Jangareddy       AC Type2       Gun A    QR-JGD-3-1  │   │
│  Gudem EV Hub     (Type2, 22kW)         ✓ Available    │   │
│                                                         │   │
│  Status: ✓ available | Last Used: 2 days ago         │   │
│  Actions: [View] [Edit] [QR Code] [Print] [Maintain]  │   │
│  ───────────────────────────────────────────────────── │   │
│                                                         │   │
│  [← Previous] 1-5 of 18 guns [Next →]                 │   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Features**:
- Table view of all charging guns
- Filter by station, status, connector type
- Search by QR code or barcode code
- Display gun number, name, and codes
- Status indicator with color coding
- Last usage timestamp
- Action buttons per gun
- QR code display/print option
- Maintenance toggle

**User Interactions**:
- Click [+ Add New Gun] → Show gun creation form
- Click [View] → Navigate to gun detail page
- Click [Edit] → Edit gun details (name, status, etc.)
- Click [QR Code] → Display and download QR code image
- Click [Print] → Print QR/barcode labels
- Click [Maintain] → Mark gun as maintenance
- Click [Resume] → Mark gun as available again
- Use status filter to show only maintenance guns

---

### Web Screen 3: Gun Details & QR Code Manager
**Purpose**: View and manage individual gun details

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ Dashboard > Charging Guns > Gun A (JGD-1-1)                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🔫 Gun Details                                             │
│  [← Back]                                                   │
│                                                             │
│  GENERAL INFO                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Station:        Jangareddy Gudem EV Hub             │   │
│  │ Connector:      DC Fast 1 (CCS2, 150kW)            │   │
│  │ Gun Number:     1                                   │   │
│  │ Gun Name:       Gun A                               │   │
│  │ Status:         ✓ Available                         │   │
│  │                 [ ] Maintenance                     │   │
│  │ Last Used:      Today, 2:30 PM                      │   │
│  │ Created:        July 15, 2026, 10:00 AM           │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  IDENTIFICATION CODES                                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ QR Code:        QR-JGD-1-1                          │   │
│  │                 [Display QR Image]                  │   │
│  │                 [Download] [Print]                  │   │
│  │                                                      │   │
│  │ Barcode Code:   BC-JGD-1-1                          │   │
│  │                 [Display Barcode Image]             │   │
│  │                 [Download] [Print]                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  USAGE STATISTICS                                           │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Total Bookings:      45                             │   │
│  │ Total Usage Time:    87 hours                       │   │
│  │ Avg Session Length:  1.9 hours                      │   │
│  │ Last 7 Days:         12 bookings                    │   │
│  │ Utilization:         68%                            │   │
│  │                                                      │   │
│  │ [View Usage Report] [Download CSV]                  │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  MAINTENANCE LOG                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Date         Status      Notes                      │   │
│  │ ────────────────────────────────────────────────── │   │
│  │ Jul 10       Maintenance Cable replacement         │   │
│  │ Jun 28       Service     Power calibration         │   │
│  │ Jun 15       Available   Monthly check-up          │   │
│  │                                                      │   │
│  │ [+ Add Maintenance Log]                             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  [Save Changes] [Cancel]                                    │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### Web Screen 4: QR Code Printing Sheet
**Purpose**: Print QR/barcode labels for physical display at charging stations

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ Dashboard > Charging Guns > Print Labels                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  📄 Print Charging Gun Labels                               │
│  [← Back]                                                   │
│                                                             │
│  Select Guns to Print:                                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Station: [Jangareddy Gudem ▼]                       │   │
│  │ Filter:  [ All Guns ] [ Available ] [ Maintenance] │   │
│  │                                                      │   │
│  │ ☑️ DC Fast 1 - Gun A (QR-JGD-1-1)                  │   │
│  │ ☑️ DC Fast 1 - Gun B (QR-JGD-1-2)                  │   │
│  │ ☑️ DC Fast 2 - Gun A (QR-JGD-2-1)                  │   │
│  │ ☑️ DC Fast 2 - Gun B (QR-JGD-2-2)                  │   │
│  │ ☑️ AC Type2 - Gun A (QR-JGD-3-1)                   │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Print Settings:                                            │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ Label Size:      [ 4x6 ] [ 3x3 ] [ 2x2 ]           │   │
│  │ Include:         ☑️ QR Code ☑️ Barcode             │   │
│  │ Paper Size:      [ A4 ] [ Letter ] [ Custom ]      │   │
│  │ Copies:          [1] per label                      │   │
│  │ Include Text:    ☑️ Gun Name ☑️ Station Name       │   │
│  │                                                      │   │
│  │ [Preview] [Print] [Download PDF]                    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  PREVIEW (First 5 labels)                                   │
│  ┌──────────┬──────────┬──────────┬──────────┬──────────┐  │
│  │┌────────┐│┌────────┐│┌────────┐│┌────────┐│┌────────┐│  │
│  ││ QR-JGD │││ QR-JGD │││ QR-JGD │││ QR-JGD │││ QR-JGD ││  │
│  ││  1-1   │││  1-2   │││  2-1   │││  2-2   │││  3-1   ││  │
│  ││ [QR]   │││ [QR]   │││ [QR]   │││ [QR]   │││ [QR]   ││  │
│  ││Gun A   │││Gun B   │││Gun A   │││Gun B   │││Gun A   ││  │
│  │└────────┘│└────────┘│└────────┘│└────────┘│└────────┘│  │
│  └──────────┴──────────┴──────────┴──────────┴──────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

### Web Screen 5: Real-Time Gun Status & Monitoring
**Purpose**: Monitor gun availability and status in real-time

**Layout**:
```
┌─────────────────────────────────────────────────────────────┐
│ Dashboard > Gun Monitoring (Real-Time)                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  🔫 Real-Time Gun Status                                    │
│  Last Updated: 2:35 PM                                      │
│  [🔄 Auto-Refresh: ON] [⏸️ Pause] [📊 Export]              │
│                                                             │
│  STATIONS OVERVIEW                                          │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🏢 Jangareddy Gudem EV Hub     (Guns: 5)            │   │
│  │                                                      │   │
│  │ 🔌 DC Fast 1 (CCS2, 150kW)                          │   │
│  │    ✓ Gun A (QR-JGD-1-1)   Available    0/24h       │   │
│  │    ✓ Gun B (QR-JGD-1-2)   Available    0/24h       │   │
│  │                                                      │   │
│  │ 🔌 DC Fast 2 (CCS2, 150kW)                          │   │
│  │    ✓ Gun A (QR-JGD-2-1)   Available    0/24h       │   │
│  │    🔧 Gun B (QR-JGD-2-2)  Maintenance  -           │   │
│  │       [Resume] [Details]                            │   │
│  │                                                      │   │
│  │ 🔌 AC Type2 (Type2, 22kW)                           │   │
│  │    ✓ Gun A (QR-JGD-3-1)   Available    0/24h       │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ 🏢 Visakhapatnam Charging Hub   (Guns: 3)           │   │
│  │                                                      │   │
│  │ 🔌 Tesla Supercharger (Tesla, 250kW)                │   │
│  │    ✓ Gun A (QR-VIZ-1-1)   Available    0/24h       │   │
│  │                                                      │   │
│  │ 🔌 CCS2 Fast (CCS2, 150kW)                          │   │
│  │    🔴 Gun A (QR-VIZ-2-1)  Offline     -            │   │
│  │       [Online] [Details] [Alert]                    │   │
│  │                                                      │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  STATUS SUMMARY                                             │
│  ✓ Available:   14 guns (78%)                               │
│  ⏳ In Use:      3 guns (17%)                               │
│  🔧 Maintenance: 1 gun (5%)                                │
│  🔴 Offline:    0 guns (0%)                                │
│                                                             │
│  ALERTS & NOTIFICATIONS                                     │
│  ⚠️ Gun B (JGD-2-2) marked maintenance - estimated 2 hrs   │
│  ⚠️ Connector 1 (VIZ-2-1) offline - investigating          │
│  ✓ Gun A (JGD-1-1) now available                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 COMPREHENSIVE API DOCUMENTATION

### API Base URL
```
Production: https://api.chargeconnect.com
Development: http://localhost:8000
```

### Authentication
All endpoints require Bearer token in Authorization header:
```
Authorization: Bearer <jwt_token>
```

---

## ⚡ CHARGING GUN ENDPOINTS

### 1️⃣ Scan QR Code
**Endpoint**: `GET /api/stations/gun/qr/{qr_code}`

**Description**: Lookup charging gun by QR code and get instant booking info

**Parameters**:
| Name | Type | Required | Example |
|------|------|----------|---------|
| qr_code | string | Yes | QR-JGD-1-1 |

**Request**:
```bash
GET /api/stations/gun/qr/QR-JGD-1-1
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

**Response (200 OK)**:
```json
{
  "id": 1,
  "gun_number": 1,
  "gun_name": "Gun A",
  "qr_code": "QR-JGD-1-1",
  "barcode_code": "BC-JGD-1-1",
  "status": "available",
  "last_used_at": "2026-07-18T14:30:00",
  "created_at": "2026-07-15T10:00:00",
  "updated_at": "2026-07-18T14:30:00",
  "connector_id": 1,
  "connector_name": "DC Fast 1",
  "connector_type": "CCS2",
  "power_type": "DC",
  "max_power_kw": 150,
  "price_per_kwh": 0.35,
  "price_per_minute": 0.0,
  "station_id": 1,
  "station_name": "Jangareddy Gudem EV Hub",
  "address": "Main Road, Near Bus Stand, Jangareddy Gudem, West Godavari, Andhra Pradesh",
  "latitude": 17.1200,
  "longitude": 81.3000,
  "operator_name": "ChargePoint",
  "amenities": ["WiFi", "Restroom", "Coffee", "Parking"],
  "rating": 4.8,
  "reviews_count": 245
}
```

**Error Response (404 Not Found)**:
```json
{
  "detail": "Charging gun QR code not found"
}
```

**Error Response (400 Bad Request - Unavailable)**:
```json
{
  "detail": "Charging gun is offline"
}
```

---

### 2️⃣ Scan Barcode Code
**Endpoint**: `GET /api/stations/gun/barcode/{barcode_code}`

**Description**: Lookup charging gun by barcode code

**Parameters**:
| Name | Type | Required | Example |
|------|------|----------|---------|
| barcode_code | string | Yes | BC-JGD-1-1 |

**Request**:
```bash
GET /api/stations/gun/barcode/BC-JGD-1-1
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

**Response (200 OK)**:
Same as QR code response above

**Error Response (404 Not Found)**:
```json
{
  "detail": "Charging gun barcode code not found"
}
```

---

### 3️⃣ List Guns for Connector
**Endpoint**: `GET /api/stations/{station_id}/connectors/{connector_id}/guns`

**Description**: Get all charging guns available on a specific connector

**Parameters**:
| Name | Type | Required | Example |
|------|------|----------|---------|
| station_id | integer | Yes | 1 |
| connector_id | integer | Yes | 1 |

**Request**:
```bash
GET /api/stations/1/connectors/1/guns
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

**Response (200 OK)**:
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
    "created_at": "2026-07-15T10:00:00",
    "updated_at": "2026-07-18T14:30:00"
  },
  {
    "id": 2,
    "gun_number": 2,
    "gun_name": "Gun B",
    "qr_code": "QR-JGD-1-2",
    "barcode_code": "BC-JGD-1-2",
    "status": "available",
    "last_used_at": null,
    "created_at": "2026-07-15T10:00:00",
    "updated_at": "2026-07-15T10:00:00"
  }
]
```

---

## 📅 BOOKING ENDPOINTS

### 4️⃣ Create Booking with Charging Gun
**Endpoint**: `POST /api/bookings`

**Description**: Create a new booking with optional charging gun selection

**Request Headers**:
```
Authorization: Bearer <token>
Content-Type: application/json
```

**Request Payload**:
```json
{
  "station_id": 1,
  "connector_id": 1,
  "charging_gun_id": 1,
  "vehicle_id": 5,
  "fleet_id": null,
  "start_time": "2026-07-20T10:00:00",
  "end_time": "2026-07-20T12:00:00"
}
```

**Payload Fields**:
| Field | Type | Required | Constraints |
|-------|------|----------|-------------|
| station_id | integer | Yes | Must exist in database |
| connector_id | integer | Yes | Must belong to station_id |
| charging_gun_id | integer | No | Must belong to connector_id |
| vehicle_id | integer | No | User's vehicle if not fleet |
| fleet_id | integer | No | User must be member |
| start_time | datetime | Yes | Future time, ISO 8601 |
| end_time | datetime | Yes | After start_time, max 24h |

**Full Request Example**:
```bash
curl -X POST http://localhost:8000/api/bookings \
  -H "Authorization: Bearer eyJhbGc..." \
  -H "Content-Type: application/json" \
  -d '{
    "station_id": 1,
    "connector_id": 1,
    "charging_gun_id": 1,
    "vehicle_id": 5,
    "fleet_id": null,
    "start_time": "2026-07-20T10:00:00",
    "end_time": "2026-07-20T12:00:00"
  }'
```

**Response (201 Created)**:
```json
{
  "id": 15,
  "user_id": 3,
  "station_id": 1,
  "connector_id": 1,
  "charging_gun_id": 1,
  "vehicle_id": 5,
  "fleet_id": null,
  "status": "confirmed",
  "start_time": "2026-07-20T10:00:00Z",
  "end_time": "2026-07-20T12:00:00Z",
  "pricing_snapshot": {
    "price_per_kwh": 0.35,
    "price_per_minute": 0.0,
    "max_power_kw": 150,
    "captured_at": "2026-07-18T15:30:00"
  },
  "created_at": "2026-07-18T15:30:00Z",
  "updated_at": "2026-07-18T15:30:00Z"
}
```

**Error Response (400 Bad Request - Time Invalid)**:
```json
{
  "detail": "end_time must be after start_time"
}
```

**Error Response (400 Bad Request - Slot Taken)**:
```json
{
  "detail": "Time slot already booked"
}
```

**Error Response (400 Bad Request - Gun Unavailable)**:
```json
{
  "detail": "Charging gun is maintenance"
}
```

**Error Response (403 Forbidden - Not Fleet Member)**:
```json
{
  "detail": "You are not a member of this fleet"
}
```

---

### 5️⃣ Get My Bookings
**Endpoint**: `GET /api/bookings`

**Description**: List all bookings for the current user with full details including gun info

**Query Parameters**:
| Name | Type | Required | Example |
|------|------|----------|---------|
| status | string | No | confirmed, pending, cancelled |
| limit | integer | No | 10 |
| offset | integer | No | 0 |

**Request**:
```bash
GET /api/bookings?status=confirmed&limit=20
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

**Response (200 OK)**:
```json
[
  {
    "id": 15,
    "user_id": 3,
    "station_id": 1,
    "connector_id": 1,
    "charging_gun_id": 1,
    "vehicle_id": 5,
    "status": "confirmed",
    "start_time": "2026-07-20T10:00:00Z",
    "end_time": "2026-07-20T12:00:00Z",
    "station_name": "Jangareddy Gudem EV Hub",
    "station_address": "Main Road, Near Bus Stand, Jangareddy Gudem, West Godavari, Andhra Pradesh",
    "connector_name": "DC Fast 1",
    "connector_type": "CCS2",
    "power_type": "DC",
    "max_power_kw": 150,
    "gun_name": "Gun A",
    "qr_code": "QR-JGD-1-1",
    "barcode_code": "BC-JGD-1-1",
    "created_at": "2026-07-18T15:30:00Z"
  },
  {
    "id": 14,
    "user_id": 3,
    "station_id": 2,
    "connector_id": 3,
    "charging_gun_id": 4,
    "vehicle_id": 5,
    "status": "pending",
    "start_time": "2026-07-21T14:30:00Z",
    "end_time": "2026-07-21T16:30:00Z",
    "station_name": "Visakhapatnam Charging Hub",
    "station_address": "Port Road, Visakhapatnam, Andhra Pradesh",
    "connector_name": "AC Type2",
    "connector_type": "Type2",
    "power_type": "AC",
    "max_power_kw": 22,
    "gun_name": "Gun B",
    "qr_code": "QR-VIZ-2-2",
    "barcode_code": "BC-VIZ-2-2",
    "created_at": "2026-07-18T14:00:00Z"
  }
]
```

---

### 6️⃣ Get Booking Details
**Endpoint**: `GET /api/bookings/{booking_id}`

**Description**: Get specific booking details with full context

**Parameters**:
| Name | Type | Required | Example |
|------|------|----------|---------|
| booking_id | integer | Yes | 15 |

**Request**:
```bash
GET /api/bookings/15
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

**Response (200 OK)**:
```json
{
  "id": 15,
  "user_id": 3,
  "station_id": 1,
  "connector_id": 1,
  "charging_gun_id": 1,
  "vehicle_id": 5,
  "fleet_id": null,
  "status": "confirmed",
  "start_time": "2026-07-20T10:00:00Z",
  "end_time": "2026-07-20T12:00:00Z",
  "station_name": "Jangareddy Gudem EV Hub",
  "station_address": "Main Road, Near Bus Stand, Jangareddy Gudem, West Godavari, Andhra Pradesh",
  "connector_name": "DC Fast 1",
  "connector_type": "CCS2",
  "power_type": "DC",
  "max_power_kw": 150,
  "gun_name": "Gun A",
  "qr_code": "QR-JGD-1-1",
  "barcode_code": "BC-JGD-1-1",
  "pricing_snapshot": {
    "price_per_kwh": 0.35,
    "price_per_minute": 0.0,
    "max_power_kw": 150,
    "captured_at": "2026-07-18T15:30:00"
  },
  "created_at": "2026-07-18T15:30:00Z",
  "updated_at": "2026-07-18T15:30:00Z"
}
```

**Error Response (404 Not Found)**:
```json
{
  "detail": "Booking not found"
}
```

---

### 7️⃣ Cancel Booking
**Endpoint**: `PATCH /api/bookings/{booking_id}/cancel`

**Description**: Cancel a pending or confirmed booking

**Parameters**:
| Name | Type | Required | Example |
|------|------|----------|---------|
| booking_id | integer | Yes | 15 |

**Request**:
```bash
PATCH /api/bookings/15/cancel
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

**Response (200 OK)**:
```json
{
  "message": "Booking cancelled successfully"
}
```

**Error Response (400 Bad Request - Cannot Cancel)**:
```json
{
  "detail": "Cannot cancel booking with status in_progress"
}
```

**Error Response (404 Not Found)**:
```json
{
  "detail": "Booking not found"
}
```

---

## 📍 STATION & CONNECTOR ENDPOINTS

### 8️⃣ Get All Stations with Guns
**Endpoint**: `GET /api/stations`

**Description**: List all charging stations with optional gun information

**Query Parameters**:
| Name | Type | Required | Example |
|------|------|----------|---------|
| include_connectors | boolean | No | true |
| include_guns | boolean | No | true |
| limit | integer | No | 20 |
| offset | integer | No | 0 |

**Request**:
```bash
GET /api/stations?include_connectors=true&include_guns=true
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

**Response (200 OK)**:
```json
[
  {
    "id": 1,
    "name": "Jangareddy Gudem EV Hub",
    "address": "Main Road, Near Bus Stand, Jangareddy Gudem, West Godavari, Andhra Pradesh",
    "latitude": 17.1200,
    "longitude": 81.3000,
    "operator_name": "ChargePoint",
    "amenities": ["WiFi", "Restroom", "Coffee", "Parking"],
    "status": "active",
    "rating": 4.8,
    "reviews_count": 245,
    "connectors": [
      {
        "id": 1,
        "name": "DC Fast 1",
        "connector_type": "CCS2",
        "power_type": "DC",
        "max_power_kw": 150,
        "price_per_kwh": 0.35,
        "price_per_minute": 0.0,
        "status": "available",
        "charging_guns": [
          {
            "id": 1,
            "gun_number": 1,
            "gun_name": "Gun A",
            "qr_code": "QR-JGD-1-1",
            "barcode_code": "BC-JGD-1-1",
            "status": "available",
            "last_used_at": "2026-07-18T14:30:00"
          },
          {
            "id": 2,
            "gun_number": 2,
            "gun_name": "Gun B",
            "qr_code": "QR-JGD-1-2",
            "barcode_code": "BC-JGD-1-2",
            "status": "available",
            "last_used_at": null
          }
        ]
      },
      {
        "id": 2,
        "name": "DC Fast 2",
        "connector_type": "CCS2",
        "power_type": "DC",
        "max_power_kw": 150,
        "price_per_kwh": 0.35,
        "price_per_minute": 0.0,
        "status": "available",
        "charging_guns": [
          {
            "id": 3,
            "gun_number": 1,
            "gun_name": "Gun A",
            "qr_code": "QR-JGD-2-1",
            "barcode_code": "BC-JGD-2-1",
            "status": "available",
            "last_used_at": "2026-07-17T10:15:00"
          },
          {
            "id": 4,
            "gun_number": 2,
            "gun_name": "Gun B",
            "qr_code": "QR-JGD-2-2",
            "barcode_code": "BC-JGD-2-2",
            "status": "maintenance",
            "last_used_at": "2026-07-18T09:00:00"
          }
        ]
      }
    ]
  }
]
```

---

### 9️⃣ Get Nearby Stations with Guns
**Endpoint**: `GET /api/stations/nearby`

**Description**: Find charging stations near user location sorted by distance

**Query Parameters**:
| Name | Type | Required | Example |
|------|------|----------|---------|
| lat | float | Yes | 17.1200 |
| lng | float | Yes | 81.3000 |
| include_connectors | boolean | No | true |
| include_guns | boolean | No | true |
| radius_km | integer | No | 10 |

**Request**:
```bash
GET /api/stations/nearby?lat=17.1200&lng=81.3000&include_connectors=true&include_guns=true&radius_km=10
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

**Response (200 OK)**:
```json
[
  {
    "id": 1,
    "name": "Jangareddy Gudem EV Hub",
    "address": "Main Road, Near Bus Stand, Jangareddy Gudem, West Godavari, Andhra Pradesh",
    "latitude": 17.1200,
    "longitude": 81.3000,
    "distance_km": 0.5,
    "operator_name": "ChargePoint",
    "amenities": ["WiFi", "Restroom", "Coffee", "Parking"],
    "status": "active",
    "rating": 4.8,
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
            "status": "available",
            "last_used_at": "2026-07-18T14:30:00"
          }
        ]
      }
    ]
  },
  {
    "id": 2,
    "name": "Visakhapatnam Charging Hub",
    "address": "Port Road, Visakhapatnam, Andhra Pradesh",
    "latitude": 17.6869,
    "longitude": 83.2185,
    "distance_km": 2.3,
    "operator_name": "TeslaSupercharger",
    "amenities": ["Restaurant", "WiFi", "Restroom"],
    "status": "active",
    "rating": 4.6,
    "connectors": [
      {
        "id": 3,
        "name": "Tesla Supercharger",
        "connector_type": "Tesla",
        "power_type": "DC",
        "max_power_kw": 250,
        "price_per_kwh": 0.40,
        "status": "available",
        "charging_guns": [
          {
            "id": 5,
            "gun_number": 1,
            "gun_name": "Gun A",
            "qr_code": "QR-VIZ-1-1",
            "barcode_code": "BC-VIZ-1-1",
            "status": "available",
            "last_used_at": "2026-07-18T13:15:00"
          }
        ]
      }
    ]
  }
]
```

---

## 🔐 AUTHENTICATION ENDPOINTS

### 🔟 Login
**Endpoint**: `POST /api/auth/login`

**Request Payload**:
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

**Response (200 OK)**:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "id": 3,
    "email": "user@example.com",
    "name": "Rajesh Kumar",
    "role": "user"
  }
}
```

**Error Response (401 Unauthorized)**:
```json
{
  "detail": "Invalid email or password"
}
```

---

### 1️⃣1️⃣ Register
**Endpoint**: `POST /api/auth/register`

**Request Payload**:
```json
{
  "email": "newuser@example.com",
  "password": "SecurePassword123!",
  "name": "Priya Sharma",
  "phone": "+91-9876543210"
}
```

**Response (201 Created)**:
```json
{
  "id": 10,
  "email": "newuser@example.com",
  "name": "Priya Sharma",
  "phone": "+91-9876543210",
  "role": "user",
  "created_at": "2026-07-18T15:45:00Z"
}
```

---

## 🚗 VEHICLE ENDPOINTS

### 1️⃣2️⃣ Get User Vehicles
**Endpoint**: `GET /api/users/me/vehicles`

**Description**: Get all vehicles associated with current user

**Request**:
```bash
GET /api/users/me/vehicles
Authorization: Bearer eyJhbGc...
Content-Type: application/json
```

**Response (200 OK)**:
```json
[
  {
    "id": 5,
    "user_id": 3,
    "vehicle_type": "Electric",
    "model": "Tesla Model 3",
    "year": 2020,
    "license_plate": "TG-01-AB-1234",
    "battery_capacity": 75,
    "status": "active",
    "created_at": "2026-07-10T12:00:00Z"
  },
  {
    "id": 6,
    "user_id": 3,
    "vehicle_type": "Electric",
    "model": "Hyundai Kona Electric",
    "year": 2022,
    "license_plate": "TG-02-CD-5678",
    "battery_capacity": 64,
    "status": "active",
    "created_at": "2026-07-15T08:30:00Z"
  }
]
```

---

## 💰 BILLING ENDPOINTS

### 1️⃣3️⃣ Get Invoice
**Endpoint**: `GET /api/billing/invoices/{invoice_id}`

**Description**: Get detailed billing invoice for a booking

**Response (200 OK)**:
```json
{
  "id": 1,
  "booking_id": 15,
  "user_id": 3,
  "station_name": "Jangareddy Gudem EV Hub",
  "amount_charged": 7.35,
  "currency": "INR",
  "status": "paid",
  "billing_date": "2026-07-20",
  "due_date": "2026-07-27",
  "line_items": [
    {
      "description": "DC Fast Charging (Gun A) - 2 hours",
      "quantity": 20,
      "unit": "kWh",
      "unit_price": 0.35,
      "subtotal": 7.00
    },
    {
      "description": "Tax (5%)",
      "quantity": 1,
      "unit": "INR",
      "unit_price": 0.35,
      "subtotal": 0.35
    }
  ],
  "payment_method": "Credit Card (****1234)",
  "created_at": "2026-07-20T12:15:00Z"
}
```

---

## ❌ COMMON ERROR RESPONSES

### 401 Unauthorized
```json
{
  "detail": "Not authenticated"
}
```

### 403 Forbidden
```json
{
  "detail": "Not enough permissions"
}
```

### 404 Not Found
```json
{
  "detail": "Resource not found"
}
```

### 409 Conflict (Time Slot Conflict)
```json
{
  "detail": "Time slot already booked"
}
```

### 422 Unprocessable Entity (Validation Error)
```json
{
  "detail": [
    {
      "loc": ["body", "start_time"],
      "msg": "Invalid datetime format",
      "type": "value_error"
    }
  ]
}
```

### 429 Too Many Requests
```json
{
  "detail": "Rate limit exceeded. Please try again in 60 seconds."
}
```

### 500 Internal Server Error
```json
{
  "detail": "Internal server error. Please try again later."
}
```

---

## 📊 STATUS CODES SUMMARY

| Code | Meaning |
|------|---------|
| 200 | OK - Request successful |
| 201 | Created - Resource created successfully |
| 204 | No Content - Successful deletion |
| 400 | Bad Request - Invalid input |
| 401 | Unauthorized - Missing/invalid token |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 409 | Conflict - Time slot/resource conflict |
| 422 | Unprocessable Entity - Validation failed |
| 429 | Too Many Requests - Rate limited |
| 500 | Internal Server Error - Server issue |

---

## 🔄 REQUEST/RESPONSE FLOW DIAGRAM

```
USER APP
  ↓
[Scan QR] → GET /api/stations/gun/qr/{qr_code}
  ↓
[Gun Details Displayed]
  ↓
[Select Time & Vehicle]
  ↓
[Confirm Booking]
  ↓
POST /api/bookings
{station_id, connector_id, charging_gun_id, vehicle_id, start_time, end_time}
  ↓
[Backend Validation]
  ├─ Gun status check
  ├─ Time slot conflict check
  ├─ Fleet membership check (if applicable)
  └─ Pricing snapshot creation
  ↓
RESPONSE 201 Created
{booking_id, status: "confirmed", pricing_snapshot}
  ↓
[Booking Confirmed Screen]
  ↓
[User Gets Directions to Station]
  ↓
[At Station: Scan Booking QR Code]
  ↓
GET /api/bookings/{booking_id}
  ↓
[Start Charging]
```

---

## 🎯 USER INTERACTION FLOWS

### Flow 1: Quick QR Scan & Book
```
Home Screen
    ↓
[📱 Scan QR Code]
    ↓
QR Scanner Screen
    ↓
User points camera at gun QR code
    ↓
Gun Details Screen (Auto-populated)
    ↓
[✓ Book This Gun]
    ↓
Booking Details Screen (Pre-filled)
    ↓
[Select Vehicle, Time, Confirm]
    ↓
Confirmation Screen
    ↓
[View Booking / Home]
```

### Flow 2: Nearby Discovery & Book
```
Home Screen
    ↓
[📍 Find Nearby Stations]
    ↓
Nearby Stations Screen
    ↓
User sees stations with available guns
    ↓
[Book Now] on specific gun
    ↓
Booking Details Screen
    ↓
[Select Time, Vehicle, Confirm]
    ↓
Confirmation Screen
```

### Flow 3: Manual Station Browse
```
Home Screen
    ↓
[Search Stations]
    ↓
Station List Screen
    ↓
[View Details]
    ↓
Station Details Screen (shows all guns)
    ↓
[Book Gun A] on connector
    ↓
Booking Details Screen
    ↓
[Confirm]
    ↓
Confirmation Screen
```

---

## 🎨 UI/UX Design Specifications

### Color Scheme
- **Primary**: #2563EB (Electric Blue)
- **Success**: #10B981 (Green)
- **Warning**: #F59E0B (Orange)
- **Danger**: #EF4444 (Red)
- **Available**: #10B981 (Green)
- **Maintenance**: #F59E0B (Orange)
- **Offline**: #6B7280 (Gray)
- **In Use**: #3B82F6 (Blue)

### Font Sizes
- **Header**: 28px Bold
- **Subheader**: 20px Bold
- **Body**: 16px Regular
- **Small Text**: 14px Regular
- **Mini**: 12px Regular

### Spacing
- **Padding**: 16px standard
- **Margins**: 16px between sections
- **Card Gap**: 12px

### Animations
- **Scan Success**: Subtle green pulse animation
- **Loading**: Spinner animation
- **Status Change**: Smooth color transition (300ms)
- **Screen Transitions**: Slide animation (200ms)

---

## ✅ Frontend Checklist

- [ ] Mobile home screen with quick actions
- [ ] QR code scanner with camera integration
- [ ] Barcode code scanner
- [ ] Gun details display after scan
- [ ] Nearby stations with gun listing
- [ ] Station details with all guns
- [ ] Booking form with gun pre-selection
- [ ] Booking confirmation screen
- [ ] My Bookings list with filtering
- [ ] Booking details view
- [ ] Cancel booking functionality
- [ ] Web dashboard with charts
- [ ] Charging gun management interface
- [ ] Gun maintenance marking
- [ ] QR/barcode label printing
- [ ] Real-time gun status monitoring
- [ ] User authentication
- [ ] Payment integration
- [ ] Push notifications
- [ ] Maps integration

---

This comprehensive frontend design prompt covers all screens, interactions, API responses, and user flows for the charging gun selection system. Ready for frontend development!

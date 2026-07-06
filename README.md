# EV Charge API

A FastAPI-based backend for an EV charging application. It provides authentication, user management, station discovery, bookings, charging sessions, billing, and admin content management.

## Project structure

- main.py: FastAPI application entry point
- routes/: API route modules
- middleware/: authentication and authorization helpers
- config/database.py: PostgreSQL connection setup, table creation, and seed data

## Prerequisites

Install the following before running the project:

- Python 3.11+
- PostgreSQL 14+ (or Docker if you prefer containerized PostgreSQL)
- pip
- Virtual environment support

## 1. Clone and open the project

```powershell
cd C:\path\to\evcharge
```

## 2. Create a Python virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks script execution, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## 3. Install dependencies

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Configure environment variables

Create a file named .env in the project root with the following values:

```env
DATABASE_URL=postgresql://postgres:root123@localhost:5432/evcharge
JWT_SECRET=change-this-to-a-long-random-string
JWT_ALGORITHM=HS256
ACCESS_TOKEN_MINUTES=60
REFRESH_TOKEN_DAYS=30
CORS_ORIGINS=*
MAPPLS_API_KEY=
```

Important notes:

- JWT_SECRET is required and must be a long, random, stable string.
- If you change the database credentials, update DATABASE_URL accordingly.
- MAPPLS_API_KEY is optional and only needed if you use the map integration endpoint.

## 5. Start PostgreSQL

### Option A: Local PostgreSQL installation

Create a database named evcharge and make sure PostgreSQL is running.

```sql
CREATE DATABASE evcharge;
```

### Option B: PostgreSQL with Docker

If Docker is installed, you can run PostgreSQL with:

```powershell
docker run --name evcharge-postgres -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=root123 -e POSTGRES_DB=evcharge -p 5432:5432 -d postgres:16
```

## 6. Run the application locally

Start the FastAPI server with Uvicorn:

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:

- http://127.0.0.1:8000
- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

## 7. Verify the app

Open the health endpoint:

```powershell
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"healthy"}
```

The application also exposes:

- GET /: root status
- GET /health: health check
- GET /api/health: API health check
- GET /api/config/mappls: returns the configured map API key

## 8. Database behavior on startup

When the app starts, it will:

- connect to PostgreSQL
- create required tables if they do not exist
- seed demo station and connector data if the database is empty

## 9. Authentication flow

The API supports:

- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/refresh
- POST /api/auth/logout
- GET /api/auth/me

Use the login response token in the Authorization header:

```http
Authorization: Bearer <access_token>
```

## 10. Run with Docker

Build and run the container:

```powershell
docker build -t evcharge-api .
docker run -p 10000:10000 --env-file .env evcharge-api
```

The app inside the container runs with:

```bash
uvicorn main:app --host 0.0.0.0 --port 10000
```

## 11. Deploy to Render

This repository already contains a Render configuration file for deployment.

Use the following values in Render:

- Build Command: pip install -r requirements.txt
- Start Command: uvicorn main:app --host 0.0.0.0 --port 10000
- Environment Variables:
  - DATABASE_URL
  - JWT_SECRET
  - JWT_ALGORITHM=HS256
  - ACCESS_TOKEN_EXPIRE_MINUTES=30
  - REFRESH_TOKEN_EXPIRE_DAYS=7
  - CORS_ORIGINS=*

## 12. Troubleshooting

### Module import errors

If you see dependency-related errors, reinstall requirements:

```powershell
pip install -r requirements.txt
```

### JWT_SECRET error

If the app fails with a JWT_SECRET error, make sure .env contains a valid JWT_SECRET value.

### Database connection errors

If the database connection fails:

- confirm PostgreSQL is running
- confirm the DATABASE_URL is correct
- confirm the database exists
- confirm the port 5432 is open

### Port already in use

If port 8000 or 10000 is already in use, run the server on a different port:

```powershell
uvicorn main:app --host 0.0.0.0 --port 9000 --reload
```

## 13. Example test flow

1. Start the server
2. Register a new user at /api/auth/register
3. Login at /api/auth/login
4. Copy the returned token
5. Use it to call protected endpoints

## Summary

The project is ready to run once Python, PostgreSQL, and the environment variables are configured. The fastest local path is:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

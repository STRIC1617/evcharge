# import os
import logging
from contextlib import asynccontextmanager
from datetime import datetime
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from dotenv import load_dotenv

from config.database import init_database, close_pool
from routes import auth, users, stations, bookings, sessions, billing, content, admin

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_database()
    yield
    await close_pool()

app = FastAPI(title="Charge Connect API", lifespan=lifespan, redirect_slashes=False)

origins = os.getenv("CORS_ORIGINS", "")
allow_origins = [o.strip() for o in origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]
)

app.include_router(auth.router, prefix="/api/auth")
app.include_router(users.router, prefix="/api/users")
app.include_router(stations.router, prefix="/api/stations")
app.include_router(bookings.router, prefix="/api/bookings")
app.include_router(sessions.router, prefix="/api/sessions")
app.include_router(billing.router, prefix="/api/billing")
app.include_router(content.router, prefix="/api/content")
app.include_router(admin.router, prefix="/api/admin")

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/health")
def health():
    return {"status": "healthy"}

@app.get("/api/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/config/mappls")
async def get_mappls_config():
    return {"apiKey": os.getenv("MAPPLS_API_KEY", "")}
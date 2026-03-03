from fastapi import FastAPI, Depends
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.api import router
from app.api.v1.routers.calls import ws_router
from app.core.config import settings
from app.api.deps import get_db

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS: When allow_credentials=True, allow_origins cannot be "*"
# Specify the frontend origin(s) explicitly
ALLOWED_ORIGINS = [
    # Development
    "http://localhost:5173",  # Vite dev server
    "http://localhost:3000",  # Alternative dev port
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
    # Production
    "https://remiscus.me",
    "https://www.remiscus.me",
    "https://app.remiscus.me",  # If frontend is deployed here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(router, prefix=settings.API_V1_STR)
app.include_router(ws_router)  # WebSocket routes at root level

@app.get("/")
def read_root():
    return {"message": "Welcome to the Intellipost API"}

@app.get("/db_check")
async def db_check(db:AsyncSession = Depends(get_db)):
    try:
        result= await db.execute(text("SELECT 1"))

        result.scalar()
        return{
            "status":"healthy",
            "database":"connected"
        }
    except Exception as e:
        return {
            "status":"unhealthy",
            "database":"disconnected",
            "error":str(e)
        }
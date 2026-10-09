from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from identity_service.api import router
from identity_service.database import engine
from identity_service.settings import IdentitySettings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = IdentitySettings.load()
    app.state.email_delivery_ready = settings.email_ready
    yield
    engine.dispose()


app = FastAPI(title="DataShield Identity", version="1.0.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health", tags=["Health"])
def health():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(503, "Identity database unavailable")
    settings = IdentitySettings.load()
    return {"status": "ok", "database": "postgresql" if engine.dialect.name == "postgresql" else engine.dialect.name,
            "email_verification_required": settings.email_verify_required,
            "email_delivery_ready": settings.email_ready}

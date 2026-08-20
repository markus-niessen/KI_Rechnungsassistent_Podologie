from fastapi import FastAPI

from app.core.config import get_settings
from app.db.base import Base
import app.db.models  # noqa: F401
from app.db.session import engine
from app.routes.patients import router as patients_router
from app.routes.services import router as services_router
from app.routes.business_profiles import router as business_profiles_router
from app.routes.invoices import router as invoices_router
from app.routes.payments import router as payments_router

app = FastAPI(title=get_settings().app_name)

Base.metadata.create_all(bind=engine)
app.include_router(patients_router)
app.include_router(services_router)
app.include_router(business_profiles_router)
app.include_router(invoices_router)
app.include_router(payments_router)


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"message": "KI Rechnungsassistent für Podologie"}

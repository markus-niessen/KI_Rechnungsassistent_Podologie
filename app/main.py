from fastapi import FastAPI

from app.core.config import get_settings

app = FastAPI(title=get_settings().app_name)


@app.get("/health", tags=["system"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", tags=["system"])
def root() -> dict[str, str]:
    return {"message": "KI Rechnungsassistent für Podologie"}


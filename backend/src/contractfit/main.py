from fastapi import FastAPI

from contractfit.config import get_settings

settings = get_settings()

app = FastAPI(
    title="ContractFit API",
    version="0.1.0",
    description="Evidence-grounded government opportunity matching for facilities contractors.",
)


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}

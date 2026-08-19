import logging

from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers import accounts, transfers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

app=FastAPI(
    title="LEDGER_API",
    description="Double entry ledger with transactional outbox event publishing",
    version="1.0.0"
)

app.include_router(accounts.router, tags=["accounts"])
app.include_router(transfers.router, tags=["transfers"])

@app.get("/health", tags=["ops"])
def health(db: Session=Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "OK"}
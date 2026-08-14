from sqlalchemy.orm import Session
from sqlalchemy import func, case
from app import models

def get_balance(db: Session, account_id)-> int:
    result=db.query(
        func.coalesce(
            func.sum(
                case(
                    (models.LedgerEntry.direction=="credit", models.LedgerEntry.amount),
                    else_=-models.LedgerEntry.amount,
                )
            ),
            0,
        )
    ).filter(models.LedgerEntry.account_id==account_id).scalar()
    return result

def find_existing_transfer(db:Session, idempotency_key: str):
    return db.query(models.Transfer).filter(
        models.Transfer.idempotency_key==idempotency_key
    ).first()

def find_existing_ledger_entry(db:Session, idempotency_key: str):
    return db.query(models.LedgerEntry).filter(
        models.LedgerEntry.idempotency_key==idempotency_key
    ).first()


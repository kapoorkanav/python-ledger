import uuid
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas, crud, events

router=APIRouter()

@router.post("/transfers")
def create_transfer(request: schemas.TransferRequest, db: Session=Depends(get_db)):
    existing=crud.find_existing_transfer(db, request.idempotency_key)
    if existing:
        return{
            "transfer_id": str(existing.id),
            "from_balance": crud.get_balance(db, existing.from_account_id),
            "to_balance": crud.get_balance(db, existing.to_account_id),
        }
    if request.from_account_id==request.to_account_id:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same account")
    account_ids=sorted([request.from_account_id, request.to_account_id], key=str)

    locked_accounts=(
        db.query(models.Account)
        .filter(models.Account.id.in_(account_ids))
        .with_for_update()
        .order_by(models.Account.id)
        .all()
    )

    if len(locked_accounts)!=2:
        raise HTTPException(status_code=404, detail="One or both accounts not found")

    existing = crud.find_existing_transfer(db, request.idempotency_key)
    if existing:
        return{
            "transfer_id": str(existing.id),
            "from_balance": crud.get_balance(db, existing.from_account_id),
            "to_balance": crud.get_balance(db, existing.to_account_id),
        }

    current_balance=crud.get_balance(db, request.from_account_id)
    if current_balance<request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    transfer_id=uuid.uuid4()

    debit_entry=models.LedgerEntry(
        account_id=request.from_account_id,
        transfer_id=transfer_id,
        amount=request.amount,
        direction="debit",
        idempotency_key=f"{request.idempotency_key}-out",
    )

    credit_entry=models.LedgerEntry(
        account_id=request.to_account_id,
        transfer_id=transfer_id,
        amount=request.amount,
        direction="credit",
        idempotency_key=f"{request.idempotency_key}-in",
    )

    transfer_record=models.Transfer(
        id=transfer_id,
        from_account_id=request.from_account_id,
        to_account_id=request.to_account_id,
        amount=request.amount,
        idempotency_key=request.idempotency_key,
    )

    db.add_all([debit_entry, credit_entry, transfer_record])
    db.flush()
    final_from_balance = crud.get_balance(db, request.from_account_id)
    final_to_balance = crud.get_balance(db, request.to_account_id)
    db.commit()

    events.publish_transfer_completed(
        transfer_id=transfer_id,
        from_account_id=request.from_account_id,
        to_account_id=request.to_account_id,
        amount=request.amount,
    )

    return {
        "transfer_id": str(transfer_id),
        "from_balance": final_from_balance,
        "to_balance": final_to_balance,
    }
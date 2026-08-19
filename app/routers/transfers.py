import uuid
import json
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app import models, schemas, crud, events, idempotency
from sqlalchemy.exc import IntegrityError
from app.auth import require_api_key



router=APIRouter()

def _replay_or_none(db:Session, request: schemas.TransferRequest):
    existing=crud.find_existing_transfer(db, request.idempotency_key)

    if existing is None:
        return None
    if(
        existing.from_account_id!=request.from_account_id
        or existing.to_account_id!=request.to_account_id
        or existing.amount!=request.amount
    ):
        raise HTTPException(
            status_code=409,
            detail="Idempotency key already used with different parameters"
        )
    return {
        "transfer_id": str(existing.id),
        "from_balance": crud.get_balance(db, existing.from_account_id),
        "to_balance": crud.get_balance(db, existing.to_account_id),
    }


@router.post("/transfers", response_model=schemas.TransferResponse, dependencies=[Depends(require_api_key)])
def create_transfer(request: schemas.TransferRequest, db: Session=Depends(get_db)):
    replay=_replay_or_none(db, request)

    if replay:
        return replay

    if request.to_account_id==request.from_account_id:
        raise HTTPException(status_code=400, detail="Cannot transfer to the same account")

    locked_accounts=(
        db.query(models.Account)
        .filter(models.Account.id.in_([request.from_account_id, request.to_account_id]))
        .order_by(models.Account.id)
        .with_for_update()
        .all()
    )

    if len(locked_accounts)!=2:
        raise HTTPException(status_code=404, detail="One or both accounts not found")

    accounts_by_id={account.id: account for account in locked_accounts}

    if accounts_by_id[request.from_account_id].currency != accounts_by_id[request.to_account_id].currency:
        raise HTTPException(
            status_code=400,
            detail="Cannot transfer between accounts in different currencies",
        )
    
    replay=_replay_or_none(db, request)
    
    if replay:
        return replay

    current_balance=crud.get_balance(db, request.from_account_id)
    if current_balance<request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    transfer_id=uuid.uuid4()

    debit_entry=models.LedgerEntry(
        account_id=request.from_account_id,
        transfer_id=transfer_id,
        amount=request.amount,
        direction="debit",
        idempotency_key=idempotency.entry_key(idempotency.TRANSFER, request.idempotency_key, "debit"),
    )

    credit_entry=models.LedgerEntry(
        account_id=request.to_account_id,
        transfer_id=transfer_id,
        amount=request.amount,
        direction="credit",
        idempotency_key=idempotency.entry_key(idempotency.TRANSFER, request.idempotency_key, "credit"),
    )

    transfer_record=models.Transfer(
        id=transfer_id,
        from_account_id=request.from_account_id,
        to_account_id=request.to_account_id,
        amount=request.amount,
        idempotency_key=request.idempotency_key,
    )

    outbox_event=models.OutboxEvent(
        event_type="TransferCompleted",
        payload=json.dumps({
            "transfer_id": str(transfer_id),
            "from_account_id": str(request.from_account_id),
            "to_account_id": str(request.to_account_id),
            "amount": request.amount,
        }),
    )

    db.add(outbox_event)
    db.add_all([debit_entry, credit_entry])
    db.add(transfer_record)
    db.flush()
    final_from_balance = crud.get_balance(db, request.from_account_id)
    final_to_balance = crud.get_balance(db, request.to_account_id)
    
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Idempotency key already in use")

    return {
        "transfer_id": str(transfer_id),
        "from_balance": final_from_balance,
        "to_balance": final_to_balance,
    }
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.database import get_db
from app import models, schemas, idempotency
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from app.auth import require_api_key

router=APIRouter()

EXTERNAL_ACCOUNT_PREFIX="EXTERNAL:"

def get_or_create_external_account(db: Session, currency: str="USD")-> models.Account:
    name=f"{EXTERNAL_ACCOUNT_PREFIX}{currency}"

    db.execute(
        pg_insert(models.Account)
        .values(id=uuid.uuid4(), name=name, currency=currency)
        .on_conflict_do_nothing(
            index_elements=["name"],
            index_where=text("name LIKE 'EXTERNAL:%'"),
        )
    )
    db.flush()
    return db.query(models.Account).filter(models.Account.name==name).one()

def _replay_or_none(db: Session, entry_key: str, account_id: uuid.UUID, amount: int):
    existing=crud.find_existing_ledger_entry(db, entry_key)
    if existing is None:
        return None
    if existing.account_id!=account_id or existing.amount!=amount:
        raise HTTPException(
            status_code=409,
            detail="Idempotency key already used with different parameters",
        )
    return {"account_id": account_id, "balance": crud.get_balance(db, account_id)}


@router.post("/accounts", response_model=schemas.AccountOut, status_code=201)
def create_account(account: schemas.AccountCreate, db: Session=Depends(get_db)):
    db_account=models.Account(name=account.name, currency=account.currency)
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return {
        "id": db_account.id,
        "name": db_account.name,
        "currency": db_account.currency,
        "balance": 0
    }

@router.get("/accounts/{account_id}", response_model=schemas.AccountOut, status_code=200)
def get_account(account_id: uuid.UUID, db: Session=Depends(get_db)):
    account=db.query(models.Account).filter(models.Account.id==account_id).first()
    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )
    balance=crud.get_balance(db, account_id)
    return {
        "id": account.id,
        "name": account.name,
        "currency": account.currency,
        "balance": balance
    }

@router.post("/accounts/{account_id}/deposit", response_model=schemas.DepositResponse, dependencies=[Depends(require_api_key)])
def deposit(account_id: uuid.UUID, request: schemas.DepositRequest, db: Session=Depends(get_db)):
    account_leg=idempotency.entry_key(idempotency.DEPOSIT, request.idempotency_key, "credit")
    external_leg=idempotency.entry_key(idempotency.DEPOSIT, request.idempotency_key, "debit")

    replay=_replay_or_none(db, account_leg, account_id, request.amount)

    if replay:
        return replay
    
    account=(
        db.query(models.Account)
        .filter(models.Account.id==account_id)
        .with_for_update()
        .first()
    )
    
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    replay=_replay_or_none(db, account_leg, account_id, request.amount)

    if replay:
        return replay

    external=get_or_create_external_account(db, account.currency)
    operation_id=uuid.uuid4()

    db.add_all([
        models.LedgerEntry(
            account_id=external.id, transfer_id=operation_id, amount=request.amount,
            direction="debit", idempotency_key=external_leg,
        ),
        models.LedgerEntry(
            account_id=account_id, transfer_id=operation_id, amount=request.amount,
            direction="credit", idempotency_key=account_leg,
        ),
    ])

    db.flush()
    balance=crud.get_balance(db, account_id)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Idempotency key is already in use")

    return {"account_id": account_id, "balance": balance}



@router.post("/accounts/{account_id}/withdraw", response_model=schemas.WithdrawalResponse, dependencies=[Depends(require_api_key)])
def withdraw(account_id: uuid.UUID, request: schemas.WithdrawalRequest, db: Session=Depends(get_db)):
    account_leg=idempotency.entry_key(idempotency.WITHDRAW, request.idempotency_key, "debit")
    external_leg=idempotency.entry_key(idempotency.WITHDRAW, request.idempotency_key, "credit")

    replay=_replay_or_none(db, account_leg, account_id, request.amount)

    if replay:
        return replay

    account=(
        db.query(models.Account)
        .filter(models.Account.id==account_id)
        .with_for_update()
        .first()
    )

    if not account:
        raise HTTPException(status_code=404, detail="Account not found")

    replay=_replay_or_none(db, account_leg, account_id, request.amount)

    if replay:
        return replay

    if crud.get_balance(db, account_id)<request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    external=get_or_create_external_account(db, account.currency)

    operation_id=uuid.uuid4()

    db.add_all([
        models.LedgerEntry(
            account_id=account_id, transfer_id=operation_id, amount=request.amount,
            direction="debit", idempotency_key=account_leg
        ),
        models.LedgerEntry(
            account_id=external.id, transfer_id=operation_id, amount=request.amount,
            direction="credit", idempotency_key=external_leg
        ),
    ])
    db.flush()

    balance=crud.get_balance(db, account_id)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Idempotency key already in use")

    return {"account_id": account_id, "balance": balance}
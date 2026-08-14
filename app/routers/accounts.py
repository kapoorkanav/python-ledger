import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app import crud
from app.database import get_db
from app import models, schemas

router=APIRouter()

def get_or_create_external_account(db: Session)-> models.Account:
    account=db.query(models.Account).filter(models.Account.name=="EXTERNAL").first()
    if not account:
        account=models.Account(name="EXTERNAL", currency="USD")
        db.add(account)
        db.flush()
    return account


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
            detail="Acount not found"
        )
    balance=crud.get_balance(db, account_id)
    return {
        "id": account.id,
        "name": account.name,
        "currency": account.currency,
        "balance": balance
    }

@router.post("/accounts/{account_id}/deposit", response_model=schemas.DepositResponse)
def deposit(account_id: uuid.UUID, request: schemas.DepositRequest, db: Session=Depends(get_db)):
    existing=crud.find_existing_ledger_entry(db, f"{request.idempotency_key}-out")
    if existing:
        return{
            "account_id": account_id,
            "balance": crud.get_balance(db, account_id),
        }
    account=db.query(models.Account).filter(models.Account.id==account_id).with_for_update().first()
    existing=crud.find_existing_ledger_entry(db, f"{request.idempotency_key}-out")
    if existing:
        return{
            "account_id": account_id,
            "balance": crud.get_balance(db, account_id),
        }
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    external=get_or_create_external_account(db)
    transfer_id=uuid.uuid4()

    debit_entry=models.LedgerEntry(
        account_id=external.id,
        transfer_id=transfer_id,
        amount=request.amount,
        direction="debit",
        idempotency_key=f"{request.idempotency_key}-out",
    )

    credit_entry=models.LedgerEntry(
        account_id=account_id,
        transfer_id=transfer_id,
        amount=request.amount,
        direction="credit",
        idempotency_key=f"{request.idempotency_key}-in",
    )
    db.add_all([debit_entry, credit_entry])
    db.flush()
    balance=crud.get_balance(db, account.id)
    db.commit()
    return {"account_id": str(account.id), "balance": balance}

@router.post("/accounts/{account_id}/withdraw", response_model=schemas.WithdrawalResponse)
def withdraw(account_id: uuid.UUID, request: schemas.WithdrawalRequest, db: Session=Depends(get_db)):
    existing=crud.find_existing_ledger_entry(db, f"{request.idempotency_key}-out")
    if existing:
        return{
            "account_id": account_id,
            "balance": crud.get_balance(db, account_id),
        }
    account=db.query(models.Account).filter(models.Account.id==account_id).with_for_update().first()
    existing=crud.find_existing_ledger_entry(db, f"{request.idempotency_key}-out")
    if existing:
        return{
            "account_id": account_id,
            "balance": crud.get_balance(db, account_id),
        }
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    current_balance=crud.get_balance(db, account_id)
    if current_balance<request.amount:
        raise HTTPException(status_code=400, detail="Insufficient Balance")
    external=get_or_create_external_account(db)
    transfer_id=uuid.uuid4()

    debit_entry=models.LedgerEntry(
        account_id=account_id,
        transfer_id=transfer_id,
        amount=request.amount,
        direction="debit",
        idempotency_key=f"{request.idempotency_key}-out",
    )

    credit_entry=models.LedgerEntry(
        account_id=external.id,
        transfer_id=transfer_id,
        amount=request.amount,
        direction="credit",
        idempotency_key=f"{request.idempotency_key}-in",
    )

    db.add_all([debit_entry, credit_entry])
    db.flush()
    balance=crud.get_balance(db, account_id)
    db.commit()
    return {"account_id": str(account.id), "balance": balance}
import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class AccountCreate(BaseModel):
    name: str
    currency: str="USD"

class AccountOut(BaseModel):
    id: uuid.UUID
    name: str
    currency: str
    balance: int

    class Config:
        from_attributes=True

class DepositRequest(BaseModel):
    amount: int=Field(gt=0)
    idempotency_key: str
    
class DepositResponse(BaseModel):
    account_id: uuid.UUID
    balance: int

class WithdrawalRequest(BaseModel):
    amount: int=Field(gt=0)
    idempotency_key: str

class WithdrawalResponse(BaseModel):
    account_id: uuid.UUID
    balance: int

class TransferRequest(BaseModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: int=Field(gt=0)
    idempotency_key: str

class TransferResponse(BaseModel):
    transfer_id: uuid.UUID
    from_balance: int
    to_balance: int

class LedgerEntryOut(BaseModel):
    id: uuid.UUID
    transfer_id: uuid.UUID
    amount: int
    direction: str
    created_at: datetime

    class Config:
        from_attributes=True

class TransferOut(BaseModel):
    id: uuid.UUID
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: int
    status: str
    created_at: datetime

    class Config:
        from_attributes=True
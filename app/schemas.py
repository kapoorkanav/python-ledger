import uuid
from pydantic import BaseModel

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
    amount: int
    idempotency_key: str
    
class DepositResponse(BaseModel):
    account_id: uuid.UUID
    balance: int

class WithdrawalRequest(BaseModel):
    amount: int
    idempotency_key: str

class WithdrawalResponse(BaseModel):
    account_id: uuid.UUID
    balance: int

class TransferRequest(BaseModel):
    from_account_id: uuid.UUID
    to_account_id: uuid.UUID
    amount: int
    idempotency_key: str
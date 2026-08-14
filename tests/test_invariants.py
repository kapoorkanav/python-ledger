from app.database import Base
from sqlalchemy import create_engine, func, case
from sqlalchemy.orm import sessionmaker
from app import models, crud
from hypothesis import given, strategies as st, settings

operation_strategy=st.fixed_dictionaries({
    "kind": st.sampled_from(["deposit", "withdraw"]),
    "amount": st.integers(min_value=1, max_value=500),
})

operations_strategy=st.lists(operation_strategy, min_size=1, max_size=30)

TEST_DATABASE_URL="postgresql://ledger_user:ledger_pass@localhost:5432/ledger_db"
engine=create_engine(TEST_DATABASE_URL)
SessionLocal=sessionmaker(bind=engine)

@settings(max_examples=50, deadline=None)
@given(operations_strategy)
def test_ledger_always_balances(operations):
    db=SessionLocal()
    try:
        account=models.Account(name="Hypothesis-Test")
        db.add(account)
        db.flush()

        for op in operations:
            external=db.query(models.Account).filter(models.Account.name=="EXTERNAL_HYP").first()
            if not external:
                external=models.Account(name="EXTERNAL_HYP")
                db.add(external)
                db.flush()
            balance=crud.get_balance(db, account.id)
            if op["kind"]=="withdraw" and balance<op["amount"]:
                continue
            import uuid
            transfer_id=uuid.uuid4()
            if op["kind"]=="deposit":
                from_acc, to_acc=external.id, account.id
            else:
                from_acc, to_acc=account.id, external.id
            db.add_all([
                models.LedgerEntry(account_id=from_acc, transfer_id=transfer_id, amount=op["amount"], direction="debit", idempotency_key=str(uuid.uuid4())),
                models.LedgerEntry(account_id=to_acc, transfer_id=transfer_id, amount=op["amount"], direction="credit", idempotency_key=str(uuid.uuid4())),
            ])
            db.flush()
        
        total=db.query(
            func.sum(case((models.LedgerEntry.direction=="credit", models.LedgerEntry.amount),
            else_=-models.LedgerEntry.amount,)
            )
        ).filter(
            models.LedgerEntry.account_id.in_([account.id, external.id])
        ).scalar() or 0
        assert total==0
    finally:
        db.rollback()
        db.close()
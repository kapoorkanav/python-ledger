import uuid
from sqlalchemy import Column, String, BigInteger, ForeignKey, DateTime, CheckConstraint, func, Boolean, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base

class Account(Base):
    __tablename__="accounts"

    id=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name=Column(String, nullable=False)
    currency=Column(String, nullable=False, default="USD")
    created_at=Column(DateTime(timezone=True), server_default=func.now())

    entries=relationship("LedgerEntry", back_populates="account")

    __table_args__=(
        Index(
            "uq_external_account_per_currency",
            "name",
            unique=True,
            postgresql_where=text("name LIKE 'EXTERNAL:%'"),
        ),
    )

class LedgerEntry(Base):
    __tablename__="ledger_entries"

    id=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id=Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False, index=True)
    transfer_id=Column(UUID(as_uuid=True), nullable=False)
    amount=Column(BigInteger, nullable=False)
    direction=Column(String, nullable=False)
    idempotency_key=Column(String, unique=True, nullable=True)
    created_at=Column(DateTime(timezone=True), server_default=func.now())

    account=relationship("Account", back_populates="entries")

    __table_args__=(
        CheckConstraint("direction IN ('debit', 'credit')", name="valid_direction"),
        CheckConstraint("amount > 0", name="positive_amount"),
    )

class Transfer(Base):
    __tablename__="transfers"
    id=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    from_account_id=Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    to_account_id=Column(UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=False)
    amount=Column(BigInteger, nullable=False)
    status=Column(String, nullable=False, default="completed")
    idempotency_key=Column(String, unique=True, nullable=False)
    created_at=Column(DateTime(timezone=True), server_default=func.now())

    __table_args__=(
        CheckConstraint("amount > 0", name="positive_transfer_amount"),
    )

class OutboxEvent(Base):
    __tablename__="outbox_events"
    id=Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type=Column(String, nullable=False)
    payload=Column(String, nullable=False)
    published=Column(Boolean, nullable=False, default=False)
    published_at=Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    failed = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    last_error = Column(String, nullable=True)
    created_at=Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # The relay only ever polls for rows still awaiting delivery.
        Index(
            "ix_outbox_events_pending",
            "created_at",
            postgresql_where=text("published = false AND failed = false"),
        ),
    )


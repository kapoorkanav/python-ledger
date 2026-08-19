import json

from app import models

def test_transfer_writes_outbox_event(client, db_session, account, key):
    alice, bob = account("Alice"), account("Bob")
    client.post(f"/accounts/{alice['id']}/deposit",
                json={"amount": 5000, "idempotency_key": key("dep")})

    response = client.post("/transfers", json={
        "from_account_id": alice["id"], "to_account_id": bob["id"],
        "amount": 1000, "idempotency_key": key("tx"),
    })
    assert response.status_code == 200
    transfer_id = response.json()["transfer_id"]

    outbox_entry = (
        db_session.query(models.OutboxEvent)
        .filter(models.OutboxEvent.payload.contains(transfer_id))
        .one()
    )
    assert outbox_entry.event_type == "TransferCompleted"
    assert outbox_entry.published is False
    assert outbox_entry.failed is False
    assert outbox_entry.attempts == 0
    assert json.loads(outbox_entry.payload) == {
        "transfer_id": transfer_id,
        "from_account_id": alice["id"],
        "to_account_id": bob["id"],
        "amount": 1000,
    }

def test_failed_transfer_writes_no_outbox_event(client, db_session, account, key):
    """The outbox row and the ledger entries commit together or not at all."""
    alice, bob = account("Alice"), account("Bob")
    before = db_session.query(models.OutboxEvent).count()

    response = client.post("/transfers", json={
        "from_account_id": alice["id"], "to_account_id": bob["id"],
        "amount": 1000, "idempotency_key": key("tx"),
    })

    assert response.status_code == 400
    assert db_session.query(models.OutboxEvent).count() == before
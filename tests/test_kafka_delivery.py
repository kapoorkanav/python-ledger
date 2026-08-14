from kafka import KafkaConsumer
import json
import os
import pytest

@pytest.mark.integration
def test_transfer_event_actually_delivered_to_kafka(client):
    consumer=KafkaConsumer(
        "transfers.completed",
        bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        auto_offset_reset="latest",
        consumer_timeout_ms=10000,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )
    # Establish the "latest" offset before publishing the transfer; otherwise
    # the first poll can occur after publishing and skip the new event.
    consumer.poll(timeout_ms=1000)

    alice = client.post("/accounts", json={"name": "Alice"}).json()
    bob = client.post("/accounts", json={"name": "Bob"}).json()
    client.post(f"/accounts/{alice['id']}/deposit", json={"amount": 5000, "idempotency_key": "kd1"})

    transfer = client.post("/transfers", json={
        "from_account_id": alice["id"], "to_account_id": bob["id"],
        "amount": 1200, "idempotency_key": "kt1",
    }).json()

    received = [msg.value for msg in consumer]
    consumer.close()

    assert any(
        event["transfer_id"] == transfer["transfer_id"]
        and event["amount"] == 1200
        for event in received
    )

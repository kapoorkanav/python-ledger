import json
import os
import uuid
import time

import pytest
from kafka import KafkaConsumer

from app import events, models
from app.outbox_relay import relay_once

@pytest.mark.integration
def test_relay_publishes_outbox_event_to_broker(db_session):
    transfer_id=str(uuid.uuid4())
    payload={
        "transfer_id": transfer_id,
        "from_account_id": str(uuid.uuid4()),
        "to_account_id": str(uuid.uuid4()),
        "amount": 1200,
    }

    outbox_event=models.OutboxEvent(
        event_type="TransferCompleted",
        payload=json.dumps(payload),
    )
    db_session.add(outbox_event)
    db_session.flush()

    for _ in range(20):
        relay_once(db_session)
        db_session.refresh(outbox_event)
        if outbox_event.published:
            break
        time.sleep(0.5)

    assert outbox_event.published is True
    assert outbox_event.published_at is not None
    assert outbox_event.attempts==0
    assert outbox_event.failed is False


    consumer=KafkaConsumer(
        events.topic_for("TransferCompleted"),
        bootstrap_servers=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
        auto_offset_reset="earliest",
        group_id=f"test-group-{uuid.uuid4()}",
        consumer_timeout_ms=10000,
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
    )

    try:
        delivered=[m.value for m in consumer if m.value.get("transfer_id")==transfer_id]
        assert len(delivered)>=1
        assert delivered[0]["amount"]==1200

    finally:
        consumer.close()

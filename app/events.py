import os
import json
from kafka import KafkaProducer

KAFKA_BOOTSTRAP_SERVERS=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

_producer=None

def get_producer():
    global _producer
    if _producer is None:
        _producer=KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
        )
    return _producer

def publish_transfer_completed(transfer_id, from_account_id, to_account_id, amount):
    try:
        producer=get_producer()
        event={
            "event_type": "Transfer Completed",
            "transfer_id": str(transfer_id),
            "from_account_id": str(from_account_id),
            "to_account_id": str(to_account_id),
            "amount": amount,
        }
        producer.send("transfers.completed", value=event)
        producer.flush()
    except Exception as e:
        print(f"Failed to publish kafka event {e}")
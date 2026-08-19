import os
import json
from kafka import KafkaProducer

KAFKA_BOOTSTRAP_SERVERS=os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
PUBLISH_TIMEOUT_SECONDS=10

TOPIC_BY_EVENT_TYPE={
    "TransferCompleted": "transfers.completed"
}

class UnknownEventTypeError(Exception):
    """Raised when an outbox row carries an unmapped event type."""

def topic_for(event_type: str)->str:
    try:
        return TOPIC_BY_EVENT_TYPE[event_type]
    except KeyError as exc:
        raise UnknownEventTypeError(event_type) from exc

_producer=None

def get_producer():
    global _producer
    if _producer is None:
        _producer=KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode("utf-8"),
            acks="all",
            retries=5,
            max_in_flight_requests_per_connection=1,
            linger_ms=5,
        )
    return _producer

def publish_raw(event_type: str, payload: dict, key: str|None=None):
    producer=get_producer()
    future=producer.send(
        topic_for(event_type),
        value=payload,
        key=key.encode("utf-8") if key else None,
    )
    future.get(timeout=PUBLISH_TIMEOUT_SECONDS)
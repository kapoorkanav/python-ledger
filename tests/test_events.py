import pytest

from app import events


def test_known_event_type_maps_to_topic():
    assert events.topic_for("TransferCompleted") == "transfers.completed"


def test_unknown_event_type_raises():
    with pytest.raises(events.UnknownEventTypeError):
        events.topic_for("SomethingElseHappened")
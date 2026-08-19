import time
import json
import logging
from sqlalchemy.orm import Session
from datetime import datetime, timezone


from app.database import SessionLocal
from app import models, events

logger=logging.getLogger(__name__)

BATCH_SIZE=10
MAX_ATTEMPTS=5
POLL_INTERVAL_SECONDS=2

def relay_once(db: Session)->int:
    pending=(
        db.query(models.OutboxEvent)
        .filter(
            models.OutboxEvent.published.is_(False),
            models.OutboxEvent.failed.is_(False),
        )
        .order_by(models.OutboxEvent.created_at)
        .with_for_update(skip_locked=True)
        .limit(BATCH_SIZE)
        .all()
    )

    published_count=0

    for event in pending:
        payload=json.loads(event.payload)

        try:
            events.publish_raw(event.event_type, payload, key=payload.get("transfer_id"))

        except Exception as exc:
            event.attempts+=1
            event.last_error=str(exc)[:500]
            if event.attempts>=MAX_ATTEMPTS:
                event.failed=True
                logger.error(
                    "outbox event %s permanently failed after %d attempts: %s",
                    event.id, event.attempts, exc,
                )
            else:
                logger.warning(
                    "outbox event %s publish failed (attempt %d/%d): %s",
                    event.id, event.attempts, MAX_ATTEMPTS, exc,
                )
            continue
        event.published=True
        event.published_at=datetime.now(timezone.utc)
        published_count+=1
    db.commit()
    return published_count

def run_forever():
    logger.info("outbox relay started")
    
    while True:
        db=SessionLocal()
        try:
            published=relay_once(db)
            if published:
                logger.info("relayed %d event(s)", published)
        except Exception:
            logger.exception("relay iteration failed")
            db.rollback()
        finally:
            db.close()
        time.sleep(POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    run_forever()
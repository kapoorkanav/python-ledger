# python-ledger

A double-entry ledger API: accounts, deposits, withdrawals, and transfers, backed by Postgres, with a Kafka transactional outbox for downstream event delivery.

Every movement of money is two ledger rows, a debit and a credit, never a mutated balance column. A balance is a query, not a stored value. That single decision is what the rest of this document is really about.

## Contents

- [Data model](#data-model)
- [Why balances are derived, not stored](#why-balances-are-derived-not-stored)
- [Concurrency: locking and deadlock avoidance](#concurrency-locking-and-deadlock-avoidance)
- [Idempotency](#idempotency)
- [The transactional outbox](#the-transactional-outbox)
- [Auth](#auth)
- [API](#api)
- [Running it](#running-it)
- [Testing](#testing)
- [Deliberately out of scope](#deliberately-out-of-scope)

## Data model

| Table | Purpose |
|---|---|
| `accounts` | `id`, `name`, `currency`. One reserved row per currency (`EXTERNAL:USD`, `EXTERNAL:EUR`, ...) acts as the clearing account for deposits and withdrawals — see below. |
| `ledger_entries` | The source of truth. Every deposit, withdrawal, and transfer writes exactly two rows here: one `debit`, one `credit`, always equal in amount. `CHECK` constraints enforce `amount > 0` and `direction IN ('debit','credit')` at the database layer, not just in application code. |
| `transfers` | One row per account-to-account transfer, for lookup and idempotency tracking. Deposits and withdrawals don't get a row here, they're modeled as transfers against the `EXTERNAL` account instead. |
| `outbox_events` | Events waiting to be published to Kafka. Written in the same transaction as the ledger entries that caused them. See [The transactional outbox](#the-transactional-outbox). |

## Why balances are derived, not stored

There is no `balance` column anywhere. `GET /accounts/{id}` computes it on read:

```sql
SELECT COALESCE(SUM(CASE WHEN direction = 'credit' THEN amount ELSE -amount END), 0)
FROM ledger_entries WHERE account_id = :account_id
```

A stored balance and the entries that justify it can drift — a bug, a manual fix, a partial failure, and now the two disagree with no way to tell which one is wrong. Deriving the balance from the entries makes that category of bug structurally impossible: the entries **are** the balance, there's nothing else to drift.

Deposits and withdrawals reuse the same double-entry mechanism as transfers, against a reserved `EXTERNAL:<currency>` account — a deposit is a transfer *from* `EXTERNAL`, a withdrawal is a transfer *to* it. One code path, one set of invariants, instead of a parallel "simple" implementation for deposits that has to independently get concurrency and idempotency right a second time. The `EXTERNAL` account for each currency is created lazily and race-safely, via `INSERT ... ON CONFLICT DO NOTHING` against a partial unique index (`name LIKE 'EXTERNAL:%'`) — two concurrent first-ever deposits in the same currency can't create two clearing accounts.

A transfer between two different-currency accounts is rejected outright (`400`) — there's no conversion logic here, and silently treating `100 USD` and `100 EUR` as equal would be a real bug, not a missing feature.

## Concurrency: locking and deadlock avoidance

A transfer locks both accounts with a single query:

```python
db.query(models.Account)
  .filter(models.Account.id.in_([from_id, to_id]))
  .order_by(models.Account.id)
  .with_for_update()
  .all()
```

The `order_by` is load-bearing, not decorative. Postgres acquires row locks in the order rows are returned, and `ORDER BY id` means *every* transfer — regardless of which account is "from" and which is "to" — locks accounts in the same global order. Two opposing transfers (A→B and B→A) racing each other therefore serialize instead of deadlocking: whichever one locks the lower-ID account first proceeds, the other queues behind it. `test_opposing_transfers_do_not_deadlock` exercises this directly — 20 transfers in alternating directions, all expected to eventually succeed, with a conservation check that the combined balance across both accounts never changes.

Deposits and withdrawals take a single row lock (`SELECT ... FOR UPDATE`) on the one real account involved before checking balance and writing entries, so concurrent withdrawals against the same account can't both read a stale balance and both succeed — `test_concurrent_withdrawals_never_overdraw` fires 20 concurrent withdrawals against a balance that can only cover 10, and asserts exactly 10 succeed.

## Idempotency

Every write endpoint takes an `idempotency_key` and is safe to retry. The key that actually gets stored is namespaced by **operation and leg**, not the raw client-supplied string:

```
{operation}:{client_key}-{leg}     e.g.  deposit:pay-123-credit
```

This matters because a deposit and a withdrawal write to *different* rows for the *same* logical operation — without namespacing, a client reusing the same key across a deposit and a later withdrawal (a natural pattern if keys are derived from a business ID, which is the standard advice) would make the withdrawal look like an already-processed replay of the deposit, and silently no-op. Namespacing by operation means that collision can't happen by construction.

Replay handling is checked twice: once before acquiring the row lock (cheap early exit for the common case), and once after (closes the race where two identical requests arrive concurrently). If a key is reused with *different* parameters — same key, different amount — that's rejected with `409`, not silently treated as a fresh operation or silently replayed with stale data. The database-level `UNIQUE` constraint on `idempotency_key` is the real backstop underneath both checks: even if the application-level check somehow raced past correctly, the constraint makes a true duplicate write impossible, converted to a `409` on `IntegrityError`.

## The transactional outbox

A transfer writes its `OutboxEvent` row in the **same database transaction** as its ledger entries:

```python
db.add(outbox_event)
db.add_all([debit_entry, credit_entry])
db.add(transfer_record)
db.commit()   # one commit — all of it lands, or none of it does
```

This is what makes "publish an event when a transfer completes" actually reliable. Publishing directly to Kafka inside the request would create a window where the transfer commits but the publish fails (or vice versa) — the two systems can't be made atomic with each other directly. Writing the event to the same Postgres transaction as the transfer sidesteps the problem entirely: there's only one thing to commit.

A separate process, `outbox_relay`, polls for unpublished rows and delivers them:

```python
db.query(OutboxEvent)
  .filter(published=False, failed=False)
  .order_by(created_at)
  .with_for_update(skip_locked=True)
  .limit(10)
```

`SKIP LOCKED` is what lets this run as more than one instance without instances fighting over the same rows — each relay grabs whatever isn't currently locked by another and moves on, rather than blocking. Publish failures are retried with an attempt counter; after 5 failed attempts a row is marked `failed` rather than retried forever, so a permanently-broken event doesn't spin silently and indistinguishably from healthy operation. Delivery is keyed on `transfer_id`, so if an operation ever produces more than one related event, they're guaranteed to land on the same Kafka partition, in order.

This gives **at-least-once** delivery, not exactly-once — the Kafka producer here has no idempotence guarantee, so a retried publish after a transient failure can genuinely duplicate a message. Any consumer of `transfers.completed` needs to dedupe on `transfer_id`. That's a deliberate, stated trade-off, not an oversight.

## Auth

Money-moving endpoints (`deposit`, `withdraw`, `transfer`) require a shared secret via the `X-API-Key` header, checked with `hmac.compare_digest` rather than `==` to avoid a timing side-channel. Read endpoints and account creation are open.

This is intentionally minimal — a single static key, not per-caller identity or OAuth — and that's a considered scope decision, not a shortcut taken without thinking about it: "internal service" is not the same as "trusted network." The realistic risk this defends against isn't an external attacker, it's a misconfigured internal caller or a stray script hitting these endpoints in a loop — and a shared secret is enough to stop that class of accident at near-zero implementation cost. A production deployment serving untrusted or multi-tenant callers would need real per-caller identity (so a `Transfer` row could record *who* initiated it, which this doesn't do), but that's meaningfully more machinery than this project's scope calls for.

## API

| Method | Path | Auth | Notes |
|---|---|---|---|
| `POST` | `/accounts` | — | Create an account |
| `GET` | `/accounts/{id}` | — | Account details + derived balance |
| `GET` | `/accounts/{id}/entries` | — | Ledger entries for an account, newest first |
| `POST` | `/accounts/{id}/deposit` | `X-API-Key` | |
| `POST` | `/accounts/{id}/withdraw` | `X-API-Key` | |
| `POST` | `/transfers` | `X-API-Key` | |
| `GET` | `/transfers/{id}` | — | Look up a transfer by ID |
| `GET` | `/health` | — | Liveness + DB connectivity check |

All write endpoints take an `idempotency_key`. Full request/response schemas are in `app/schemas.py`, or via the auto-generated docs at `/docs` once the app is running.

## Running it

```bash
docker compose up -d --build
```

Brings up Postgres, a KRaft-mode Kafka broker, the API (migrating on boot), and the outbox relay. The API listens on `localhost:8000`.

```bash
export LEDGER_API_KEY=dev-secret-key   # matches the docker-compose default
curl -X POST localhost:8000/accounts -H 'Content-Type: application/json' \
  -d '{"name":"Alice","currency":"USD"}'
```

## Testing

Two tiers, split by one rule: a test is `@pytest.mark.integration` if and only if it needs something beyond a local Postgres — a live running server, or a live Kafka broker.

```bash
# fast tier — Postgres only, runs on every push
docker compose up -d db
alembic upgrade head
pytest -m "not integration"

# full-stack tier — the whole compose stack
docker compose up -d --build
pytest -m integration
```

Both tiers talk to a real Postgres over the network — nothing here is a pure unit test with mocked I/O. What the marker actually distinguishes is infrastructure cost: whether you need one container or four. `test_invariants.py` uses Hypothesis to fuzz random sequences of deposits and withdrawals and asserts the ledger always nets to zero; `test_concurrency.py` proves the locking claims above under real thread contention against a live server, not just in isolation.

## Deliberately out of scope

- **No consumer of `transfers.completed`.** The outbox reliably publishes; nothing in this repo subscribes. Adding one (a notification log, a projection) is straightforward given the pattern already in place, but it's a separate concern from the ledger's own correctness, which is what this project is actually about.
- **No per-caller identity.** See [Auth](#auth) — a shared secret stops accidental internal misuse, not a substitute for knowing *who* moved the money.


import os
import uuid
from concurrent.futures import ThreadPoolExecutor
import httpx
import pytest

BASE_URL=os.environ.get("BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.environ.get("LEDGER_API_KEY", "dev-secret-key")
HEADERS = {"X-API-Key": API_KEY}

@pytest.mark.integration
def test_concurrent_withdrawals_never_overdraw():
    run=uuid.uuid4()

    response=httpx.post(f"{BASE_URL}/accounts", json={"name": f"conc-{run}", "currency": "USD"})
    account_id=response.json()["id"]
    dep_response=httpx.post(f"{BASE_URL}/accounts/{account_id}/deposit", json={"amount": 10000, "idempotency_key": f"conc-dep-{run}"}, headers=HEADERS)


    def attempt_withdrawal(i):
        response=httpx.post(f"{BASE_URL}/accounts/{account_id}/withdraw", json={"amount": 1000, "idempotency_key": f"concurrency-with-{run}-{i}"}, timeout=30, headers=HEADERS)
        return response.status_code
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        results=list(executor.map(attempt_withdrawal, range(20)))

    balance=httpx.get(f"{BASE_URL}/accounts/{account_id}").json()["balance"]

    successes=results.count(200)
    failures=results.count(400)

    assert successes==10
    assert failures==10
    assert balance==0

@pytest.mark.integration
def test_opposing_transfers_do_not_deadlock():
    run=uuid.uuid4()
    a,b =(
        httpx.post(f"{BASE_URL}/accounts", json={"name": f"dl-{side}-{run}"}).json()
        for side in ("a", "b")
    )
    for acc in (a,b):
        httpx.post(
            f"{BASE_URL}/accounts/{acc['id']}/deposit",
            json={"amount": 10000, "idempotency_key": f"dl-dep-{acc['id']}"},
            headers=HEADERS
        )

    def transfer(i):
        src, dst = (a, b) if i % 2 == 0 else (b, a)
        return httpx.post(f"{BASE_URL}/transfers", json={
            "from_account_id": src["id"], "to_account_id": dst["id"],
            "amount": 100, "idempotency_key": f"dl-{run}-{i}",
            },
            timeout=30,
            headers=HEADERS
        ).status_code

    with ThreadPoolExecutor(max_workers=20) as executor:
        results = list(executor.map(transfer, range(20)))

    assert all(code==200 for code in results)
    total = sum(
        httpx.get(f"{BASE_URL}/accounts/{acc['id']}").json()["balance"] for acc in (a, b)
    )
    assert total == 20000 
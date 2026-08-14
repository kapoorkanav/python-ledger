import uuid
from concurrent.futures import ThreadPoolExecutor
import httpx

BASE_URL="http://127.0.0.1:8000"

def test_concurrent_withdrawals_never_overdraw():
    response=httpx.post(f"{BASE_URL}/accounts", json={"name": "ConcurrencyTest", "currency": "USD"})
    account_id=response.json()["id"]
    run_id = uuid.uuid4()
    dep_response=httpx.post(f"{BASE_URL}/accounts/{account_id}/deposit", json={"amount": 10000, "idempotency_key": f"concurrency-dep-{run_id}"})


    def attempt_withdrawal(i):
        response=httpx.post(f"{BASE_URL}/accounts/{account_id}/withdraw", json={"amount": 1000, "idempotency_key": f"concurrency-with-{run_id}-{i}"})
        return response.status_code
    
    with ThreadPoolExecutor(max_workers=20) as executor:
        results=list(executor.map(attempt_withdrawal, range(20)))

    balance=httpx.get(f"{BASE_URL}/accounts/{account_id}").json()["balance"]

    successes=results.count(200)
    failures=results.count(400)

    assert successes==10
    assert failures==10
    assert balance==0

    
def test_deposit_increases_balance(client):
    acc=client.post("/accounts", json={"name": "Alice", "currency": "USD"}).json()

    response=client.post(f"/accounts/{acc['id']}/deposit", json={"amount": 5000, "idempotency_key": "dep-001"})

    assert response.status_code==200
    assert response.json()["balance"]==5000

def test_duplicate_does_not_increase_balance(client):
    acc=client.post("/accounts", json={"name": "Alice", "currency": "USD"}).json()

    r1=client.post(f"/accounts/{acc['id']}/deposit", json={"amount": 5000, "idempotency_key": "dep-002"})
    r2=client.post(f"/accounts/{acc['id']}/deposit", json={"amount": 5000, "idempotency_key": "dep-002"})

    assert r1.status_code==200
    assert r2.status_code==200

    assert r1.json()["balance"]==r2.json()["balance"]==5000
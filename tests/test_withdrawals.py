def test_withdrawal_decreases_balance(client):
    acc=client.post("/accounts", json={"name": "Alice", "currency": "USD"}).json()
    client.post(f"/accounts/{acc['id']}/deposit", json={"amount": 5000, "idempotency_key": "dep-001"})

    response=client.post(f"/accounts/{acc['id']}/withdraw", json={"amount": 4500, "idempotency_key": "with-001"})

    assert response.status_code==200
    assert response.json()["balance"]==500

def test_insufficient_balance_not_processed(client):
    acc=client.post("/accounts", json={"name": "Alice", "currency": "USD"}).json()
    client.post(f"/accounts/{acc['id']}/deposit", json={"amount": 5000, "idempotency_key": "dep-001"})

    response=client.post(f"/accounts/{acc['id']}/withdraw", json={"amount": 6000, "idempotency_key": "with-001"})

    assert response.status_code==400
